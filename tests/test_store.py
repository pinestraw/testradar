from __future__ import annotations

import pytest

from testradar.graph.store import (
    _deserialize_file_record,
    _deserialize_graph,
    _deserialize_import_request,
    load_graph,
    save_graph,
)
from testradar.models import FileRecord, GraphSnapshot, ImportRequest


def test_save_and_load_graph_round_trip(tmp_path):
    snapshot = GraphSnapshot(
        version=1,
        source_roots=(".",),
        files={
            "pkg/service.py": FileRecord(
                path="pkg/service.py",
                content_hash="abc",
                module="pkg.service",
                is_test=False,
                parse_error=None,
                imports=(ImportRequest(module="pkg.models"),),
                resolved_imports=("pkg/models.py",),
            ),
        },
        module_to_path={"pkg.service": "pkg/service.py"},
        reverse_edges={"pkg/models.py": ("pkg/service.py",)},
        repo_fingerprint="fingerprint",
    )
    path = tmp_path / "graph.msgpack"

    save_graph(path, snapshot)
    loaded = load_graph(path)

    assert loaded == snapshot


def test_store_deserializers_reject_invalid_payloads():
    with pytest.raises(ValueError, match="must be a mapping"):
        _deserialize_graph([])
    with pytest.raises(ValueError, match="files must be a mapping"):
        _deserialize_graph({"files": [], "version": 1, "source_roots": [], "module_to_path": {}, "repo_fingerprint": "x"})
    with pytest.raises(ValueError, match="reverse_edges must be a mapping"):
        _deserialize_graph(
            {
                "files": {},
                "version": 1,
                "source_roots": [],
                "module_to_path": {},
                "repo_fingerprint": "x",
                "reverse_edges": [],
            },
        )
    with pytest.raises(ValueError, match="file record"):
        _deserialize_file_record("pkg/service.py", [])
    with pytest.raises(ValueError, match="import request"):
        _deserialize_import_request([])
