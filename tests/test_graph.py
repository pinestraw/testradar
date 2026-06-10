from __future__ import annotations

from testradar.graph.store import load_graph
from testradar.graph.build import build_graph


def test_incremental_graph_matches_rebuild(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/models.py", "class Invoice:\n    pass\n")
    repo.write("app/service.py", "from app import models\n\nVALUE = models.Invoice\n")
    repo.write("tests/test_service.py", "from app import service\n\ndef test_value():\n    assert service.VALUE\n")
    repo.commit_all()

    first_snapshot, first_mode = repo.index()
    repo.write("app/models.py", "class Invoice:\n    status = 'open'\n")
    second_snapshot, second_mode = repo.index()
    rebuilt = build_graph(repo.config())

    assert first_mode == "full"
    assert second_mode == "incremental"
    assert second_snapshot.module_to_path == rebuilt.module_to_path
    assert second_snapshot.reverse_edges == rebuilt.reverse_edges
    assert {
        path: record.resolved_imports
        for path, record in second_snapshot.files.items()
    } == {
        path: record.resolved_imports
        for path, record in rebuilt.files.items()
    }
    assert second_snapshot.repo_fingerprint == rebuilt.repo_fingerprint


def test_generic_dynamic_import_detector_links_string_imports(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/plugins/__init__.py", "")
    repo.write("app/plugins/alpha.py", "VALUE = 1\n")
    repo.write(
        "app/loader.py",
        """
        import importlib

        MODULE = importlib.import_module("app.plugins.alpha")
        """,
    )
    repo.write(
        "tests/test_loader.py",
        """
        from app import loader

        def test_loader():
            assert loader.MODULE
        """,
    )
    repo.commit_all()
    repo.index()

    repo.write("app/plugins/alpha.py", "VALUE = 2\n")
    result = repo.select()

    assert result.target_strings() == ["tests/test_loader.py"]


def test_corrupt_graph_store_rebuilds_instead_of_failing(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.write(
        "tests/test_service.py",
        """
        from app import service

        def test_value():
            assert service.VALUE == 1
        """,
    )
    repo.commit_all()
    repo.index()
    repo.config().graph_path.write_bytes(b"not-a-valid-msgpack-payload")

    result = repo.select()

    assert result.graph_mode == "full"
    assert result.target_strings() == []
    assert load_graph(repo.config().graph_path) is not None
