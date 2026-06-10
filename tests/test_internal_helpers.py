from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from testradar.detectors.generic import GenericDynamicImportDetector, _imported_module_from_expr
from testradar.graph.build import (
    _build_reverse_edges,
    _extract_import_requests,
    _resolve_file_imports,
    _resolve_reexport,
)
from testradar.models import FileRecord, HunkRange, ImportRequest
from testradar.nodeids import (
    _apply_import_bindings,
    _apply_assignment_bindings,
    _apply_from_import_bindings,
    _called_helper_name,
    _collect_helpers,
    _collect_module_bindings,
    _collect_source_spans,
    _collect_test_cases,
    _has_relevant_module_level_execution,
    _resolve_expr_paths,
    _resolve_helper,
    _statement_executes_calls,
    _visible_descendants_of_node,
    select_source_dependent_tests,
)
from testradar.parse import (
    _looks_like_exception_binding_target,
    _rewrite_legacy_except_line,
    _sanitize_legacy_except_syntax,
    _split_top_level_commas,
)


def test_parse_helper_branches_cover_comments_crlf_and_nested_commas():
    source = "try:\n    pass\nexcept ValueError as exc:\n    pass\n"
    assert _sanitize_legacy_except_syntax(source) == source
    assert _sanitize_legacy_except_syntax("VALUE = 1\n") == "VALUE = 1\n"

    assert _rewrite_legacy_except_line("    except (ValueError, TypeError), exc:  # note\r\n") == (
        "    except (ValueError, TypeError) as exc:  # note\r\n"
    )
    assert _rewrite_legacy_except_line("except ValueError as exc:\n") == "except ValueError as exc:\n"

    assert _split_top_level_commas("ValueError, wrapper('a,b'), {'x': 1, 'y': 2}, exc") == [
        "ValueError",
        " wrapper('a,b')",
        " {'x': 1, 'y': 2}",
        " exc",
    ]
    assert _split_top_level_commas('ValueError, "a\\\"b,c", exc') == [
        "ValueError",
        ' "a\\"b,c"',
        " exc",
    ]
    assert _rewrite_legacy_except_line("except ValueError,:\n") == "except ValueError,:\n"

    assert _looks_like_exception_binding_target("exc") is True
    assert _looks_like_exception_binding_target("_exc") is True
    assert _looks_like_exception_binding_target("TypeError") is False
    assert _looks_like_exception_binding_target("pkg.error") is False


def test_generic_dynamic_import_detector_marks_function_scope_imports_lazy():
    tree = ast.parse(
        """
import importlib
from typing import cast

MODULE = importlib.import_module("pkg.alpha")

def load():
    local = import_module("pkg.beta")
    typed: object = cast("Any", import_module("pkg.gamma"))
    return local.Widget, typed.Client
""",
    )

    detector = GenericDynamicImportDetector()
    results = {(item.module, item.names, item.is_from): item.is_eager for item in detector.detect(
        tree=tree,
        path=Path("loader.py"),
        module="pkg.loader",
    )}

    assert results[("pkg.alpha", (), False)] is True
    assert results[("pkg.beta", ("Widget",), True)] is False
    assert results[("pkg.gamma", ("Client",), True)] is False

    assert _imported_module_from_expr(None) is None
    assert _imported_module_from_expr(ast.parse("VALUE").body[0].value) is None
    assert _imported_module_from_expr(ast.parse("cast('Any')").body[0].value) is None
    assert _imported_module_from_expr(ast.parse("typing.cast('Any', loader())").body[0].value) is None


def test_graph_import_resolution_tracks_lazy_edges_separately():
    tree = ast.parse(
        """
import pkg.alpha

class Holder:
    from pkg import beta

def load():
    import pkg.gamma
""",
    )

    requests = tuple(_extract_import_requests(tree, module="helper", is_package=False))
    eager_flags = {(item.module, item.names, item.is_from): item.is_eager for item in requests}
    assert eager_flags[("pkg.alpha", (), False)] is True
    assert eager_flags[("pkg", ("beta",), True)] is True
    assert eager_flags[("pkg.gamma", (), False)] is False

    files = {
        "helper.py": FileRecord(
            path="helper.py",
            content_hash="helper",
            module="helper",
            is_test=False,
            parse_error=None,
            imports=requests,
        ),
        "tests/test_helper.py": FileRecord(
            path="tests/test_helper.py",
            content_hash="test",
            module="tests.test_helper",
            is_test=True,
            parse_error=None,
            imports=(ImportRequest(module="helper"),),
        ),
        "pkg/alpha.py": FileRecord("pkg/alpha.py", "a", "pkg.alpha", False, None, ()),
        "pkg/beta.py": FileRecord("pkg/beta.py", "b", "pkg.beta", False, None, ()),
        "pkg/gamma.py": FileRecord("pkg/gamma.py", "c", "pkg.gamma", False, None, ()),
    }
    module_map = {
        "helper": "helper.py",
        "tests.test_helper": "tests/test_helper.py",
        "pkg.alpha": "pkg/alpha.py",
        "pkg.beta": "pkg/beta.py",
        "pkg.gamma": "pkg/gamma.py",
    }

    resolved = _resolve_file_imports(files, module_map)
    reverse = _build_reverse_edges(resolved, module_map)

    assert resolved["helper.py"].resolved_imports == ("pkg/alpha.py", "pkg/beta.py", "pkg/gamma.py")
    assert resolved["helper.py"].resolved_eager_imports == ("pkg/alpha.py", "pkg/beta.py")
    assert reverse["pkg/alpha.py"] == ("helper.py",)
    assert reverse["pkg/gamma.py"] == ()


def test_graph_reexport_helper_covers_missing_and_cyclic_paths():
    assert _resolve_reexport("missing", "Value", {}, {}, seen=set()) == set()

    files = {
        "pkg/__init__.py": FileRecord(
            path="pkg/__init__.py",
            content_hash="pkg",
            module="pkg",
            is_test=False,
            parse_error=None,
            imports=(ImportRequest(module="pkg", names=("Value",), is_from=True),),
        ),
    }
    module_map = {"pkg": "pkg/__init__.py"}

    assert _resolve_reexport("pkg", "Value", module_map, files, seen={("pkg", "Value")}) == {"pkg/__init__.py"}


def test_nodeid_helper_branches_cover_bindings_and_module_execution(tmp_path):
    source_path = tmp_path / "service.py"
    source_path.write_text("VALUE = 1\n", encoding="utf-8")
    test_path = tmp_path / "test_service.py"
    test_path.write_text("def test_value():\n    assert True\n", encoding="utf-8")

    assert select_source_dependent_tests(
        test_path=test_path,
        test_relative_path="test_service.py",
        source_path=source_path,
        source_relative_path="service.py",
        source_module=None,
        hunks=(HunkRange(start=1, count=1),),
    ) is None
    assert select_source_dependent_tests(
        test_path=test_path,
        test_relative_path="test_service.py",
        source_path=source_path,
        source_relative_path="service.py",
        source_module="service",
        hunks=(),
    ) is None

    wildcard_tree = ast.parse("from app import *\n")
    bindings, wildcard = _collect_module_bindings(wildcard_tree)
    assert bindings == {}
    assert wildcard is True

    module_helpers, class_helpers = _collect_helpers(
        ast.parse(
            """
def helper():
    return 1

class TestThing:
    def support(self):
        return 2
""",
        ),
    )
    helper_node, owner = _resolve_helper(
        helper_name=("self", "support"),
        class_name="TestThing",
        module_helpers=module_helpers,
        class_helpers=class_helpers,
    )
    assert helper_node is not None
    assert owner == "TestThing"
    helper_node, owner = _resolve_helper(
        helper_name="helper",
        class_name=None,
        module_helpers=module_helpers,
        class_helpers=class_helpers,
    )
    assert helper_node is not None
    assert owner is None
    assert _resolve_helper(
        helper_name=("other", "support"),
        class_name="TestThing",
        module_helpers=module_helpers,
        class_helpers=class_helpers,
    ) == (None, None)
    assert _resolve_helper(
        helper_name="missing",
        class_name=None,
        module_helpers=module_helpers,
        class_helpers=class_helpers,
    ) == (None, None)

    assert _called_helper_name(ast.parse("self.support()").body[0].value) == ("self", "support")
    assert _called_helper_name(ast.parse("helper()").body[0].value) == ("", "helper")
    assert _called_helper_name(ast.parse("obj.support()").body[0].value) is None

    bindings_map: dict[str, str] = {}
    assert _apply_import_bindings(ast.parse("import app.service").body[0], bindings_map) is True
    assert _apply_import_bindings(ast.parse("import app.service").body[0], bindings_map) is False
    assert _apply_from_import_bindings(ast.parse("from .app import service").body[0], bindings_map) is False
    assert _apply_from_import_bindings(ast.ImportFrom(module=None, names=[], level=0), bindings_map) is False
    assert _apply_assignment_bindings(ast.parse("left = right = value").body[0], bindings_map) is False
    assert _apply_assignment_bindings(ast.parse("value = loader()").body[0], bindings_map) is False
    bindings_map["service"] = "app.service"
    assert _apply_assignment_bindings(ast.parse('typed: object = cast("Any", service)').body[0], bindings_map) is True
    assert bindings_map["typed"] == "app.service"

    assert _resolve_expr_paths(ast.parse("typed").body[0].value, bindings_map) == {"app.service"}
    assert _resolve_expr_paths(ast.parse("typed[0]").body[0].value, bindings_map) == {"app.service"}
    assert _resolve_expr_paths(ast.parse("typed.value").body[0].value, bindings_map) == {"app.service.value"}
    assert _resolve_expr_paths(ast.parse("loader()").body[0].value, bindings_map) == set()
    assert _resolve_expr_paths(None, bindings_map) == set()
    descendants = _visible_descendants_of_node(ast.parse("lambda value: value").body[0].value)
    assert isinstance(descendants[0], ast.Lambda)
    assert not any(isinstance(node, ast.FunctionDef) for node in descendants)

    source_spans = _collect_source_spans(
        ast.parse(
            """
class Worker:
    VALUE = 1

TOKEN = 2
""",
        ),
        "pkg.service",
    )
    assert [span.nodeid for span in source_spans] == ["pkg.service.Worker", "pkg.service.TOKEN"]

    test_cases = _collect_test_cases(
        ast.parse(
            """
class TestWorker:
    def test_runs(self):
        assert True
""",
        ),
        "tests/test_worker.py",
    )
    assert [case.nodeid for case in test_cases] == ["tests/test_worker.py::TestWorker::test_runs"]

    quiet_tree = ast.parse(
        textwrap.dedent(
            """
            "doc"
            from app import service
            VALUE = service
            """,
        ),
    )
    assert _has_relevant_module_level_execution(quiet_tree, {"service": "app.service"}, {"app.service"}) is False
    noisy_tree = ast.parse(
        textwrap.dedent(
            """
            from app import service
            VALUE = service.run()
            """,
        ),
    )
    assert _has_relevant_module_level_execution(noisy_tree, {"service": "app.service"}, {"app.service"}) is True
    assert _statement_executes_calls(ast.parse("VALUE = service.run()").body[0]) is True


def test_select_source_dependent_tests_tracks_self_helpers(tmp_path):
    source_path = tmp_path / "service.py"
    source_path.write_text(
        "def foo():\n    return 1\n\ndef bar():\n    return 2\n",
        encoding="utf-8",
    )
    test_path = tmp_path / "test_service.py"
    test_path.write_text(
        """
from service import foo, bar

class TestThing:
    def helper(self):
        return foo()

    def test_foo(self):
        assert self.helper() == 1

    def test_bar(self):
        assert bar() == 2
""".strip(),
        encoding="utf-8",
    )

    selected = select_source_dependent_tests(
        test_path=test_path,
        test_relative_path="test_service.py",
        source_path=source_path,
        source_relative_path="service.py",
        source_module="service",
        hunks=(HunkRange(start=1, count=1),),
    )

    assert selected == ["test_service.py::TestThing::test_foo"]
