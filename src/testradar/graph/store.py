from __future__ import annotations

from pathlib import Path

import msgpack

from testradar.models import FileRecord, GraphSnapshot, ImportRequest


def load_graph(path: Path) -> GraphSnapshot | None:
    if not path.exists():
        return None
    try:
        payload = msgpack.unpackb(path.read_bytes(), raw=False)
        return _deserialize_graph(payload)
    except (
        KeyError,
        TypeError,
        ValueError,
        msgpack.ExtraData,
        msgpack.FormatError,
        msgpack.StackError,
        msgpack.UnpackException,
    ):
        return None


def save_graph(path: Path, snapshot: GraphSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": snapshot.version,
        "source_roots": list(snapshot.source_roots),
        "files": {
            relative_path: {
                "path": record.path,
                "content_hash": record.content_hash,
                "module": record.module,
                "is_test": record.is_test,
                "parse_error": record.parse_error,
                "imports": [
                    {
                        "module": item.module,
                        "names": list(item.names),
                        "is_from": item.is_from,
                    }
                    for item in record.imports
                ],
                "resolved_imports": list(record.resolved_imports),
            }
            for relative_path, record in snapshot.files.items()
        },
        "module_to_path": snapshot.module_to_path,
        "reverse_edges": {key: list(value) for key, value in snapshot.reverse_edges.items()},
        "repo_fingerprint": snapshot.repo_fingerprint,
        "updated_paths": list(snapshot.updated_paths),
        "metadata": snapshot.metadata,
    }
    path.write_bytes(msgpack.packb(payload, use_bin_type=True))


def _deserialize_graph(payload: object) -> GraphSnapshot:
    if not isinstance(payload, dict):
        raise ValueError("Graph payload must be a mapping")

    raw_files = payload["files"]
    if not isinstance(raw_files, dict):
        raise ValueError("Graph payload files must be a mapping")
    files = {
        relative_path: _deserialize_file_record(relative_path, record)
        for relative_path, record in raw_files.items()
    }

    raw_reverse_edges = payload.get("reverse_edges", {})
    if not isinstance(raw_reverse_edges, dict):
        raise ValueError("Graph payload reverse_edges must be a mapping")
    reverse_edges = {key: tuple(value) for key, value in raw_reverse_edges.items()}

    return GraphSnapshot(
        version=int(payload["version"]),
        source_roots=tuple(payload["source_roots"]),
        files=files,
        module_to_path=dict(payload["module_to_path"]),
        reverse_edges=reverse_edges,
        repo_fingerprint=str(payload["repo_fingerprint"]),
        updated_paths=tuple(payload.get("updated_paths", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def _deserialize_file_record(relative_path: str, record: object) -> FileRecord:
    if not isinstance(record, dict):
        raise ValueError(f"Graph file record for {relative_path} must be a mapping")
    return FileRecord(
        path=record["path"],
        content_hash=record["content_hash"],
        module=record.get("module"),
        is_test=record["is_test"],
        parse_error=record.get("parse_error"),
        imports=tuple(
            _deserialize_import_request(item)
            for item in record.get("imports", [])
        ),
        resolved_imports=tuple(record.get("resolved_imports", [])),
    )


def _deserialize_import_request(payload: object) -> ImportRequest:
    if not isinstance(payload, dict):
        raise ValueError("Graph import request must be a mapping")
    return ImportRequest(
        module=payload.get("module"),
        names=tuple(payload.get("names", [])),
        is_from=payload.get("is_from", False),
    )
