from __future__ import annotations

import json

import pytest

from testradar.audit import load_node_set
from testradar.cov.ingest import ingest_coverage_contexts
from testradar.cov.query import query_dynamic_contexts
from testradar.graph.invert import all_test_files, app_tests, dependent_tests, tests_under as invert_tests_under
from testradar.models import (
    AuditResult,
    FileRecord,
    GraphSnapshot,
    HunkRange,
    SelectedTarget,
    SelectionResult,
    SelectionSource,
    relative_to_root,
)
from testradar.report import selection_report


def test_models_report_and_invert_helpers(tmp_path):
    snapshot = GraphSnapshot(
        version=1,
        source_roots=(".",),
        files={
            "conftest.py": FileRecord("conftest.py", "a", None, False, None, (), ()),
            "tests/test_one.py": FileRecord("tests/test_one.py", "b", "tests.test_one", True, None, (), ()),
            "tests/pkg/test_two.py": FileRecord("tests/pkg/test_two.py", "c", "tests.pkg.test_two", True, None, (), ()),
            "pkg/tests/test_local.py": FileRecord("pkg/tests/test_local.py", "d", "pkg.tests.test_local", True, None, (), ()),
            "pkg/service.py": FileRecord("pkg/service.py", "e", "pkg.service", False, None, (), ("conftest.py",)),
        },
        module_to_path={},
        reverse_edges={"conftest.py": ("pkg/service.py",)},
        repo_fingerprint="fp",
    )
    result = SelectionResult(
        targets=[SelectedTarget(target="tests/test_one.py", source=SelectionSource.GLOBAL, reason="global")],
        reasons=["reason"],
        graph_snapshot=snapshot,
        resolved_base="abc123",
        resolved_head="def456",
        comparison_mode="three-dot-merge-base",
        full_suite=True,
        graph_mode="full",
        escalations=["parse-error"],
    )

    assert selection_report(result)["targets"][0]["source"] == "global"
    assert selection_report(result)["escalations"] == ["parse-error"]
    assert selection_report(result)["resolved_base"] == "abc123"
    assert selection_report(result)["resolved_head"] == "def456"
    assert selection_report(result)["comparison_mode"] == "three-dot-merge-base"
    assert selection_report(result)["target_count"] == 1
    assert selection_report(result)["file_target_count"] == 1
    assert selection_report(result)["nodeid_target_count"] == 0
    assert result.target_strings() == ["tests/test_one.py"]
    assert snapshot.python_paths() == {
        "conftest.py",
        "tests/test_one.py",
        "tests/pkg/test_two.py",
        "pkg/tests/test_local.py",
        "pkg/service.py",
    }
    assert dependent_tests(snapshot, "missing.py") == set()
    assert dependent_tests(snapshot, "conftest.py") == all_test_files(snapshot)
    assert invert_tests_under(snapshot, "tests/pkg") == {"tests/pkg/test_two.py"}
    assert app_tests(snapshot, "pkg") == {"pkg/tests/test_local.py", "tests/pkg/test_two.py"}
    assert relative_to_root(tmp_path, tmp_path / "nested" / "file.py") == "nested/file.py"


def test_models_and_audit_helper_properties():
    assert HunkRange(start=4, count=0).end == 4
    assert HunkRange(start=4, count=0).overlaps(1, 5) is True
    assert HunkRange(start=4, count=2).overlaps(1, 3) is False
    assert AuditResult(selected=set(), failed=set(), missed=set()).miss_rate == 0.0


def test_load_node_set_and_cov_placeholders(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert load_node_set(empty) == set()

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"unexpected": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported JSON payload"):
        load_node_set(bad)

    with pytest.raises(NotImplementedError):
        ingest_coverage_contexts()
    with pytest.raises(NotImplementedError):
        query_dynamic_contexts()
