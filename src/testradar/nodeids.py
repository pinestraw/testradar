from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from testradar.models import HunkRange, NodeSpan
from testradar.parse import parse_python_source


def select_changed_tests(path: Path, relative_path: str, hunks: tuple[HunkRange, ...]) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = parse_python_source(source, filename=relative_path)
    spans = _collect_node_spans(tree, relative_path)
    if not spans:
        return [relative_path]

    selected: set[str] = set()
    for hunk in hunks:
        span = _match_hunk(spans, hunk)
        if span is None:
            return [relative_path]
        if span.has_decorators or span.has_parametrize:
            return [relative_path]
        selected.add(span.nodeid)

    return sorted(selected) or [relative_path]


def select_source_dependent_tests(
    *,
    test_path: Path,
    test_relative_path: str,
    source_path: Path,
    source_relative_path: str,
    source_module: str | None,
    hunks: tuple[HunkRange, ...],
) -> list[str] | None:
    if source_module is None or not hunks:
        return None

    source_targets = _select_changed_source_targets(
        source_path,
        source_relative_path,
        source_module,
        hunks,
    )
    if not source_targets:
        return None

    source = test_path.read_text(encoding="utf-8")
    tree = parse_python_source(source, filename=test_relative_path)
    tests = _collect_test_cases(tree, test_relative_path)
    if not tests:
        return None

    module_bindings, wildcard_import = _collect_module_bindings(tree)
    if wildcard_import:
        return None

    helpers, class_helpers = _collect_helpers(tree)
    if _has_relevant_module_level_execution(tree, module_bindings, source_targets):
        return None

    selected: list[str] = []
    for test_case in tests:
        references, safe = _collect_test_references(
            test_case=test_case,
            module_bindings=module_bindings,
            module_helpers=helpers,
            class_helpers=class_helpers,
        )
        if not safe:
            return None
        if any(_reference_matches_target(reference, source_targets) for reference in references):
            selected.append(test_case.nodeid)

    if not selected:
        return None
    if len(selected) == len(tests):
        return [test_relative_path]
    return sorted(selected)


def _collect_node_spans(tree: ast.AST, relative_path: str) -> list[NodeSpan]:
    spans: list[NodeSpan] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            spans.append(_function_span(relative_path, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith(
                    "test_",
                ):
                    spans.append(_method_span(relative_path, node, child))
    return spans


@dataclass(frozen=True)
class _TestCase:
    nodeid: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    class_name: str | None = None


def _collect_test_cases(tree: ast.AST, relative_path: str) -> list[_TestCase]:
    tests: list[_TestCase] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            tests.append(_TestCase(nodeid=f"{relative_path}::{node.name}", node=node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    tests.append(
                        _TestCase(
                            nodeid=f"{relative_path}::{node.name}::{child.name}",
                            node=child,
                            class_name=node.name,
                        ),
                    )
    return tests


def _select_changed_source_targets(
    path: Path,
    relative_path: str,
    module_name: str,
    hunks: tuple[HunkRange, ...],
) -> set[str] | None:
    source = path.read_text(encoding="utf-8")
    tree = parse_python_source(source, filename=relative_path)
    spans = _collect_source_spans(tree, module_name)
    if not spans:
        return None

    selected: set[str] = set()
    for hunk in hunks:
        span = _match_hunk(spans, hunk)
        if span is None:
            return None
        selected.add(span.nodeid)
    return selected or None


def _collect_source_spans(tree: ast.AST, module_name: str) -> list[NodeSpan]:
    spans: list[NodeSpan] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append(
                NodeSpan(
                    nodeid=f"{module_name}.{node.name}",
                    start=_node_start(node),
                    end=node.end_lineno or node.lineno,
                    has_parametrize=False,
                    has_decorators=False,
                ),
            )
            continue
        if isinstance(node, ast.ClassDef):
            spans.append(
                NodeSpan(
                    nodeid=f"{module_name}.{node.name}",
                    start=_node_start(node),
                    end=node.end_lineno or node.lineno,
                    has_parametrize=False,
                    has_decorators=False,
                ),
            )
            continue
        target_name = _assignment_name(node)
        if target_name is None:
            continue
        spans.append(
            NodeSpan(
                nodeid=f"{module_name}.{target_name}",
                start=node.lineno,
                end=node.end_lineno or node.lineno,
                has_parametrize=False,
                has_decorators=False,
            ),
        )
    return spans


def _function_span(relative_path: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> NodeSpan:
    start = _node_start(node)
    return NodeSpan(
        nodeid=f"{relative_path}::{node.name}",
        start=start,
        end=node.end_lineno or node.lineno,
        has_parametrize=_has_parametrize(node),
        has_decorators=bool(node.decorator_list),
    )


def _method_span(
    relative_path: str,
    parent: ast.ClassDef,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> NodeSpan:
    start = _node_start(node)
    return NodeSpan(
        nodeid=f"{relative_path}::{parent.name}::{node.name}",
        start=start,
        end=node.end_lineno or node.lineno,
        has_parametrize=_has_parametrize(node),
        has_decorators=bool(node.decorator_list),
    )


def _has_parametrize(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        dotted = _call_name(decorator.func) if isinstance(decorator, ast.Call) else _call_name(decorator)
        if dotted and dotted.endswith("parametrize"):
            return True
    return False


def _node_start(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    return min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])


def _assignment_name(node: ast.stmt) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _collect_helpers(
    tree: ast.AST,
) -> tuple[dict[str, ast.FunctionDef | ast.AsyncFunctionDef], dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]]]:
    module_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    class_helpers: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test_"):
                module_helpers[node.name] = node
            continue
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
            continue
        helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("test_"):
                helpers[child.name] = child
        if helpers:
            class_helpers[node.name] = helpers
    return module_helpers, class_helpers


def _collect_module_bindings(tree: ast.AST) -> tuple[dict[str, str], bool]:
    bindings: dict[str, str] = {}
    wildcard_import = False
    changed = True
    while changed:
        changed = False
        for node in getattr(tree, "body", []):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Import):
                if _apply_import_bindings(node, bindings):
                    changed = True
                continue
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    wildcard_import = True
                    continue
                if _apply_from_import_bindings(node, bindings):
                    changed = True
                continue
            if _apply_assignment_bindings(node, bindings):
                changed = True
    return bindings, wildcard_import


def _collect_test_references(
    *,
    test_case: _TestCase,
    module_bindings: dict[str, str],
    module_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    class_helpers: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]],
) -> tuple[set[str], bool]:
    return _collect_callable_references(
        node=test_case.node,
        class_name=test_case.class_name,
        module_bindings=module_bindings,
        module_helpers=module_helpers,
        class_helpers=class_helpers,
        seen_helpers=set(),
    )


def _collect_callable_references(
    *,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_name: str | None,
    module_bindings: dict[str, str],
    module_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    class_helpers: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]],
    seen_helpers: set[tuple[str | None, str]],
) -> tuple[set[str], bool]:
    bindings = dict(module_bindings)
    safe = True
    changed = True
    while changed:
        changed = False
        for child in _visible_descendants(node.body):
            if isinstance(child, ast.Import):
                if _apply_import_bindings(child, bindings):
                    changed = True
                continue
            if isinstance(child, ast.ImportFrom):
                if any(alias.name == "*" for alias in child.names):
                    safe = False
                    continue
                if _apply_from_import_bindings(child, bindings):
                    changed = True
                continue
            if _apply_assignment_bindings(child, bindings):
                changed = True

    references = _resolved_paths(node.body, bindings)
    for fixture_name in _callable_parameter_names(node):
        helper_node, helper_class_name = _resolve_helper(
            helper_name=fixture_name,
            class_name=class_name,
            module_helpers=module_helpers,
            class_helpers=class_helpers,
        )
        if helper_node is None:
            continue
        helper_refs, helper_safe = _collect_helper_references(
            helper_name=fixture_name,
            helper_node=helper_node,
            helper_class_name=helper_class_name,
            module_bindings=module_bindings,
            module_helpers=module_helpers,
            class_helpers=class_helpers,
            seen_helpers=seen_helpers,
        )
        references.update(helper_refs)
        safe = safe and helper_safe

    for child in _visible_descendants(node.body):
        helper_name = _called_helper_name(child)
        if helper_name is None:
            continue
        helper_node, helper_class_name = _resolve_helper(
            helper_name=helper_name,
            class_name=class_name if helper_name[0] == "self" else None,
            module_helpers=module_helpers,
            class_helpers=class_helpers,
        )
        if helper_node is None:
            continue
        helper_refs, helper_safe = _collect_helper_references(
            helper_name=helper_name[1],
            helper_node=helper_node,
            helper_class_name=helper_class_name,
            module_bindings=module_bindings,
            module_helpers=module_helpers,
            class_helpers=class_helpers,
            seen_helpers=seen_helpers,
        )
        references.update(helper_refs)
        safe = safe and helper_safe

    return references, safe


def _collect_helper_references(
    *,
    helper_name: str,
    helper_node: ast.FunctionDef | ast.AsyncFunctionDef,
    helper_class_name: str | None,
    module_bindings: dict[str, str],
    module_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    class_helpers: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]],
    seen_helpers: set[tuple[str | None, str]],
) -> tuple[set[str], bool]:
    key = (helper_class_name, helper_name)
    if key in seen_helpers:
        return set(), True
    return _collect_callable_references(
        node=helper_node,
        class_name=helper_class_name,
        module_bindings=module_bindings,
        module_helpers=module_helpers,
        class_helpers=class_helpers,
        seen_helpers=seen_helpers | {key},
    )


def _callable_parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names = [arg.arg for arg in node.args.args if arg.arg != "self"]
    names.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return names


def _resolve_helper(
    *,
    helper_name: tuple[str, str] | str,
    class_name: str | None,
    module_helpers: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    class_helpers: dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]],
) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef | None, str | None]:
    if isinstance(helper_name, tuple):
        owner, method_name = helper_name
        if owner == "self" and class_name is not None:
            helper = class_helpers.get(class_name, {}).get(method_name)
            return helper, class_name if helper is not None else None
        if owner == "":
            helper = module_helpers.get(method_name)
            return helper, None if helper is not None else None
        return None, None
    helper = module_helpers.get(helper_name)
    if helper is not None:
        return helper, None
    return None, None


def _called_helper_name(node: ast.AST) -> tuple[str, str] | None:
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
        return ("self", node.func.attr)
    if isinstance(node.func, ast.Name):
        return ("", node.func.id)
    return None


def _visible_descendants(nodes: list[ast.stmt]) -> list[ast.AST]:
    items: list[ast.AST] = []
    for node in nodes:
        items.extend(_visible_descendants_of_node(node))
    return items


def _visible_descendants_of_node(node: ast.AST) -> list[ast.AST]:
    items = [node]
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        items.extend(_visible_descendants_of_node(child))
    return items


def _apply_import_bindings(node: ast.Import, bindings: dict[str, str]) -> bool:
    changed = False
    for alias in node.names:
        name = alias.asname or alias.name.split(".", 1)[0]
        target = alias.name if alias.asname else alias.name.split(".", 1)[0]
        if bindings.get(name) == target:
            continue
        bindings[name] = target
        changed = True
    return changed


def _apply_from_import_bindings(node: ast.ImportFrom, bindings: dict[str, str]) -> bool:
    if node.level:
        return False
    if node.module is None:
        return False
    changed = False
    for alias in node.names:
        name = alias.asname or alias.name
        target = f"{node.module}.{alias.name}"
        if bindings.get(name) == target:
            continue
        bindings[name] = target
        changed = True
    return changed


def _apply_assignment_bindings(node: ast.AST, bindings: dict[str, str]) -> bool:
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return False
        paths = _resolve_expr_paths(node.value, bindings)
        if len(paths) != 1:
            return False
        target = next(iter(paths))
        if bindings.get(node.targets[0].id) == target:
            return False
        bindings[node.targets[0].id] = target
        return True
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        paths = _resolve_expr_paths(node.value, bindings)
        if len(paths) != 1:
            return False
        target = next(iter(paths))
        if bindings.get(node.target.id) == target:
            return False
        bindings[node.target.id] = target
        return True
    return False


def _resolve_expr_paths(node: ast.AST | None, bindings: dict[str, str]) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        target = bindings.get(node.id)
        return {target} if target is not None else set()
    if isinstance(node, ast.Attribute):
        base_paths = _resolve_expr_paths(node.value, bindings)
        return {f"{path}.{node.attr}" for path in base_paths}
    if isinstance(node, ast.Call):
        dotted = _call_name(node.func)
        if dotted in {"cast", "typing.cast"} and len(node.args) >= 2:
            return _resolve_expr_paths(node.args[1], bindings)
        return set()
    if isinstance(node, ast.Subscript):
        return _resolve_expr_paths(node.value, bindings)
    return set()


def _resolved_paths(nodes: list[ast.stmt], bindings: dict[str, str]) -> set[str]:
    references: set[str] = set()
    for node in _visible_descendants(nodes):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Import, ast.ImportFrom)):
            continue
        references.update(_resolve_expr_paths(node, bindings))
    return references


def _has_relevant_module_level_execution(
    tree: ast.AST,
    bindings: dict[str, str],
    targets: set[str],
) -> bool:
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(
            node.value.value,
            str,
        ):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and not _statement_executes_calls(node):
            if any(_reference_matches_target(reference, targets) for reference in _resolved_paths([node], bindings)):
                continue
        if any(_reference_matches_target(reference, targets) for reference in _resolved_paths([node], bindings)):
            return True
    return False


def _statement_executes_calls(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) for child in ast.walk(node))


def _reference_matches_target(reference: str, targets: set[str]) -> bool:
    return any(reference == target or reference.startswith(f"{target}.") for target in targets)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _match_hunk(spans: list[NodeSpan], hunk: HunkRange) -> NodeSpan | None:
    matching = [span for span in spans if hunk.overlaps(span.start, span.end)]
    if len(matching) != 1:
        return None
    span = matching[0]
    if hunk.start < span.start or hunk.end > span.end:
        return None
    return span
