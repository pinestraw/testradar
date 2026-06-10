from __future__ import annotations

from dataclasses import replace

import pytest

from testradar.graph.build import (
    _best_module_match,
    _load_detectors,
    _resolve_from_module,
    _resolve_requests,
    build_graph,
    iter_repo_files,
    module_name_for_path,
    scan_repo_hashes,
    update_graph_incremental,
)
from testradar.models import FileRecord, ImportRequest


def test_iter_repo_files_ignores_special_directories(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "file.py").write_text("VALUE = 1\n", encoding="utf-8")

    paths = {path.relative_to(tmp_path).as_posix() for path in iter_repo_files(tmp_path)}

    assert paths == {"pkg/file.py"}


def test_module_name_for_path_and_relative_import_resolution(tmp_path):
    root = tmp_path.resolve()
    pkg_root = root / "src"
    pkg_root.mkdir()
    nested = pkg_root / "pkg" / "module.py"
    nested.parent.mkdir()
    nested.write_text("VALUE = 1\n", encoding="utf-8")
    init_path = pkg_root / "pkg" / "__init__.py"
    init_path.write_text("", encoding="utf-8")
    outside = root / "standalone.py"
    outside.write_text("VALUE = 1\n", encoding="utf-8")

    assert module_name_for_path(nested, (pkg_root,), root) == "pkg.module"
    assert module_name_for_path(init_path, (pkg_root,), root) == "pkg"
    assert module_name_for_path(outside, (pkg_root,), root) == "standalone"
    assert module_name_for_path(root, (pkg_root,), root) is None

    assert _resolve_from_module(current_module=None, imported_module="pkg.mod", level=1, is_package=False) == "pkg.mod"
    assert _resolve_from_module(current_module="pkg.module", imported_module=None, level=1, is_package=False) == "pkg"
    assert _resolve_from_module(current_module="pkg.module", imported_module="sub", level=2, is_package=False) == "sub"
    assert _resolve_from_module(current_module="pkg", imported_module="sub", level=1, is_package=True) == "pkg.sub"


def test_resolve_requests_and_best_module_match():
    module_map = {
        "pkg": "pkg/__init__.py",
        "pkg.alpha": "pkg/alpha.py",
        "pkg.beta": "pkg/beta.py",
    }
    files = {
        "pkg/__init__.py": FileRecord(
            path="pkg/__init__.py",
            content_hash="hash",
            module="pkg",
            is_test=False,
            parse_error=None,
            imports=(ImportRequest(module="pkg.beta", names=("Beta",), is_from=True),),
        ),
        "pkg/alpha.py": FileRecord(
            path="pkg/alpha.py",
            content_hash="hash",
            module="pkg.alpha",
            is_test=False,
            parse_error=None,
            imports=(),
        ),
        "pkg/beta.py": FileRecord(
            path="pkg/beta.py",
            content_hash="hash",
            module="pkg.beta",
            is_test=False,
            parse_error=None,
            imports=(),
        ),
    }
    requests = (
        ImportRequest(module=None),
        ImportRequest(module="pkg.alpha"),
        ImportRequest(module="pkg", names=(), is_from=True),
        ImportRequest(module="pkg", names=("alpha",), is_from=True),
        ImportRequest(module="pkg", names=("Beta",), is_from=True),
        ImportRequest(module="pkg", names=("missing",), is_from=True),
    )

    resolved = _resolve_requests(requests, module_map, files)

    assert resolved == {"pkg/__init__.py", "pkg/alpha.py", "pkg/beta.py"}
    assert _best_module_match("pkg.beta.value", module_map) == "pkg/beta.py"
    assert _best_module_match("missing", module_map) is None


def test_update_graph_incremental_rebuilds_for_version_and_source_root_changes(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.commit_all()
    snapshot, _mode = repo.index()

    wrong_version = replace(snapshot, version=snapshot.version + 1)
    rebuilt_version, mode_version = update_graph_incremental(repo.config(), wrong_version)
    assert mode_version == "full"
    assert rebuilt_version.version == snapshot.version

    wrong_roots = replace(snapshot, source_roots=("src",))
    rebuilt_roots, mode_roots = update_graph_incremental(repo.config(), wrong_roots)
    assert mode_roots == "full"
    assert rebuilt_roots.source_roots == snapshot.source_roots


def test_update_graph_incremental_handles_non_python_change_without_reparse(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.commit_all()
    snapshot, _mode = repo.index()
    repo.write("README.txt", "changed\n")

    updated, mode = update_graph_incremental(repo.config(), snapshot)

    assert mode == "incremental"
    assert updated.updated_paths == ()
    assert updated.files == snapshot.files


def test_load_detectors_supports_custom_and_rejects_invalid(repo, tmp_path, monkeypatch):
    detector_module = tmp_path / "custom_detector.py"
    detector_module.write_text(
        """
from testradar.models import ImportRequest

class CustomDetector:
    name = "custom"

    def detect(self, *, tree, path, module):
        return (ImportRequest(module="pkg.custom"),)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    custom_config = replace(repo.config(), detector_paths=("custom_detector:CustomDetector",))
    detectors = _load_detectors(custom_config)
    assert detectors[-1].name == "custom"

    invalid_config = replace(repo.config(), detector_paths=("bad-detector-path",))
    with pytest.raises(ValueError, match="module:attribute"):
        _load_detectors(invalid_config)


def test_scan_repo_hashes_and_build_graph_cover_python_and_non_python(repo):
    repo.write("pkg/__init__.py", "")
    repo.write("pkg/service.py", "import json\n")
    repo.write("notes.txt", "hello\n")
    repo.commit_all()

    file_hashes, python_hashes = scan_repo_hashes(repo.root)
    snapshot = build_graph(repo.config())

    assert "notes.txt" in file_hashes
    assert "notes.txt" not in python_hashes
    assert "pkg.service" in snapshot.module_to_path
