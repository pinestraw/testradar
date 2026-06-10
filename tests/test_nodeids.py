from __future__ import annotations

import ast

from testradar.models import HunkRange, NodeSpan
from testradar.nodeids import _call_name, _match_hunk, select_changed_tests


def test_select_changed_tests_returns_file_when_no_test_spans(tmp_path):
    path = tmp_path / "helpers.py"
    path.write_text("VALUE = 1\n", encoding="utf-8")

    assert select_changed_tests(path, "helpers.py", (HunkRange(start=1, count=1),)) == ["helpers.py"]


def test_select_changed_tests_supports_class_methods_and_async_tests(tmp_path):
    path = tmp_path / "test_case.py"
    path.write_text(
        """
class TestThing:
    async def test_async(self):
        assert True

    def test_sync(self):
        assert True
""".strip(),
        encoding="utf-8",
    )

    assert select_changed_tests(path, "test_case.py", (HunkRange(start=2, count=1),)) == [
        "test_case.py::TestThing::test_async",
    ]
    assert select_changed_tests(path, "test_case.py", (HunkRange(start=5, count=1),)) == [
        "test_case.py::TestThing::test_sync",
    ]


def test_select_changed_tests_falls_back_for_decorated_or_ambiguous_hunks(tmp_path):
    decorated = tmp_path / "test_decorated.py"
    decorated.write_text(
        """
@custom
def test_value():
    assert True
""".strip(),
        encoding="utf-8",
    )
    assert select_changed_tests(decorated, "test_decorated.py", (HunkRange(start=2, count=1),)) == [
        "test_decorated.py",
    ]

    plain = tmp_path / "test_plain.py"
    plain.write_text(
        """
def test_one():
    assert True

def test_two():
    assert True
""".strip(),
        encoding="utf-8",
    )
    assert select_changed_tests(plain, "test_plain.py", (HunkRange(start=1, count=5),)) == ["test_plain.py"]


def test_nodeid_helpers_cover_private_branches():
    spans = [
        NodeSpan(nodeid="a", start=2, end=4, has_parametrize=False, has_decorators=False),
        NodeSpan(nodeid="b", start=3, end=5, has_parametrize=False, has_decorators=False),
    ]
    assert _match_hunk(spans, HunkRange(start=3, count=1)) is None

    unique = [NodeSpan(nodeid="a", start=2, end=4, has_parametrize=False, has_decorators=False)]
    assert _match_hunk(unique, HunkRange(start=1, count=4)) is None
    assert _call_name(ast.parse("value").body[0].value) == "value"
    assert _call_name(ast.parse("pkg.value").body[0].value) == "pkg.value"
    assert _call_name(ast.parse("call().value").body[0].value) is None
