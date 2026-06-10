from __future__ import annotations

import ast
import hashlib
import importlib
import os
from pathlib import Path
from typing import Iterable, Sequence

from testradar.config import TestradarConfig
from testradar.detectors.base import CouplingDetector
from testradar.detectors.django import DjangoCouplingDetector
from testradar.detectors.generic import GenericDynamicImportDetector
from testradar.detectors.pytest import PytestPluginDetector
from testradar.models import FileRecord, GraphSnapshot, ImportRequest, relative_to_root
from testradar.policy.defaults import is_test_path

IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".testradar",
    "node_modules",
}

GRAPH_VERSION = 1


def build_graph(config: TestradarConfig) -> GraphSnapshot:
    tree_file_hashes, py_file_hashes = scan_repo_hashes(config.repo_root)
    detectors = _load_detectors(config)
    files = {
        path: _parse_file(
            config=config,
            path=config.repo_root / path,
            relative_path=path,
            content_hash=content_hash,
            detectors=detectors,
        )
        for path, content_hash in py_file_hashes.items()
    }
    module_to_path = _build_module_map(files)
    resolved_files = _resolve_file_imports(files, module_to_path)
    return GraphSnapshot(
        version=GRAPH_VERSION,
        source_roots=config.normalized_source_roots(),
        files=resolved_files,
        module_to_path=module_to_path,
        reverse_edges=_build_reverse_edges(resolved_files, module_to_path),
        repo_fingerprint=hash_fingerprint(tree_file_hashes),
        updated_paths=tuple(sorted(files)),
        metadata={"python_file_count": str(len(files))},
    )


def update_graph_incremental(
    config: TestradarConfig,
    previous: GraphSnapshot | None,
) -> tuple[GraphSnapshot, str]:
    if previous is None:
        return build_graph(config), "full"
    if previous.version != GRAPH_VERSION:
        return build_graph(config), "full"
    if previous.source_roots != config.normalized_source_roots():
        return build_graph(config), "full"

    tree_file_hashes, py_file_hashes = scan_repo_hashes(config.repo_root)
    current_fingerprint = hash_fingerprint(tree_file_hashes)
    if current_fingerprint == previous.repo_fingerprint:
        return previous, "unchanged"

    previous_hashes = {path: record.content_hash for path, record in previous.files.items()}
    changed_paths = {
        path
        for path, content_hash in py_file_hashes.items()
        if previous_hashes.get(path) != content_hash
    }
    removed_paths = set(previous.files) - set(py_file_hashes)
    if not changed_paths and not removed_paths:
        updated = GraphSnapshot(
            version=previous.version,
            source_roots=previous.source_roots,
            files=previous.files,
            module_to_path=previous.module_to_path,
            reverse_edges=previous.reverse_edges,
            repo_fingerprint=current_fingerprint,
            updated_paths=(),
            metadata=previous.metadata,
        )
        return updated, "incremental"

    detectors = _load_detectors(config)
    files = dict(previous.files)
    for path in removed_paths:
        files.pop(path, None)
    for path in changed_paths:
        files[path] = _parse_file(
            config=config,
            path=config.repo_root / path,
            relative_path=path,
            content_hash=py_file_hashes[path],
            detectors=detectors,
        )

    module_to_path = _build_module_map(files)
    resolved_files = _resolve_file_imports(files, module_to_path)
    updated = GraphSnapshot(
        version=GRAPH_VERSION,
        source_roots=config.normalized_source_roots(),
        files=resolved_files,
        module_to_path=module_to_path,
        reverse_edges=_build_reverse_edges(resolved_files, module_to_path),
        repo_fingerprint=current_fingerprint,
        updated_paths=tuple(sorted(changed_paths | removed_paths)),
        metadata={"python_file_count": str(len(resolved_files))},
    )
    return updated, "incremental"


def scan_repo_hashes(repo_root: Path) -> tuple[dict[str, str], dict[str, str]]:
    file_hashes: dict[str, str] = {}
    python_hashes: dict[str, str] = {}
    for absolute_path in iter_repo_files(repo_root):
        relative_path = relative_to_root(repo_root, absolute_path)
        digest = hash_file(absolute_path)
        file_hashes[relative_path] = digest
        if absolute_path.suffix == ".py":
            python_hashes[relative_path] = digest
    return file_hashes, python_hashes


def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    for current_root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = sorted(name for name in dir_names if name not in IGNORED_DIR_NAMES)
        for file_name in sorted(file_names):
            yield Path(current_root, file_name)


def hash_file(path: Path) -> str:
    digest = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def hash_fingerprint(file_hashes: dict[str, str]) -> str:
    digest = hashlib.blake2b(digest_size=16)
    for path in sorted(file_hashes):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hashes[path].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _load_detectors(config: TestradarConfig) -> tuple[CouplingDetector, ...]:
    detectors: list[CouplingDetector] = [GenericDynamicImportDetector(), PytestPluginDetector()]
    if "django" in config.presets:
        detectors.append(DjangoCouplingDetector())
    for detector_path in config.detector_paths:
        module_name, _, attribute = detector_path.partition(":")
        if not module_name or not attribute:
            raise ValueError(f"Detector path must look like module:attribute: {detector_path}")
        module = importlib.import_module(module_name)
        detector_cls = getattr(module, attribute)
        detectors.append(detector_cls())
    return tuple(detectors)


def _parse_file(
    *,
    config: TestradarConfig,
    path: Path,
    relative_path: str,
    content_hash: str,
    detectors: Sequence[CouplingDetector],
) -> FileRecord:
    module = module_name_for_path(path, config.source_roots, config.repo_root)
    is_package = path.name == "__init__.py"
    is_test = is_test_path(config, relative_path)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=relative_path)
    except SyntaxError as exc:
        return FileRecord(
            path=relative_path,
            content_hash=content_hash,
            module=module,
            is_test=is_test,
            parse_error=str(exc),
            imports=(),
        )

    imports = list(_extract_import_requests(tree, module=module, is_package=is_package))
    for detector in detectors:
        imports.extend(detector.detect(tree=tree, path=path, module=module))
    return FileRecord(
        path=relative_path,
        content_hash=content_hash,
        module=module,
        is_test=is_test,
        parse_error=None,
        imports=tuple(imports),
    )


def module_name_for_path(path: Path, source_roots: tuple[Path, ...], repo_root: Path) -> str | None:
    candidates: list[Path] = []
    for root in sorted(source_roots, key=lambda item: len(item.parts), reverse=True):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        candidates.append(root)
    base_root = candidates[0] if candidates else repo_root
    relative_path = path.relative_to(base_root)
    if relative_path == Path("."):
        return None
    parts = list(relative_path.with_suffix("").parts)
    if not parts:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def _extract_import_requests(
    tree: ast.AST,
    *,
    module: str | None,
    is_package: bool,
) -> Iterable[ImportRequest]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield ImportRequest(module=alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved_module = _resolve_from_module(
                current_module=module,
                imported_module=node.module,
                level=node.level,
                is_package=is_package,
            )
            names = tuple(alias.name for alias in node.names)
            yield ImportRequest(module=resolved_module, names=names, is_from=True)


def _resolve_from_module(
    *,
    current_module: str | None,
    imported_module: str | None,
    level: int,
    is_package: bool,
) -> str | None:
    if level == 0:
        return imported_module
    if current_module is None:
        return imported_module
    if is_package:
        package_parts = current_module.split(".")
    else:
        package_parts = current_module.split(".")[:-1]
    trim = max(level - 1, 0)
    if trim:
        package_parts = package_parts[: max(len(package_parts) - trim, 0)]
    if imported_module:
        package_parts.extend(imported_module.split("."))
    return ".".join(part for part in package_parts if part) or None


def _build_module_map(files: dict[str, FileRecord]) -> dict[str, str]:
    module_map: dict[str, str] = {}
    for path, record in files.items():
        if record.module:
            module_map[record.module] = path
    return module_map


def _resolve_file_imports(
    files: dict[str, FileRecord],
    module_to_path: dict[str, str],
) -> dict[str, FileRecord]:
    resolved: dict[str, FileRecord] = {}
    for path, record in files.items():
        resolved_imports = sorted(_resolve_requests(record.imports, module_to_path))
        resolved[path] = FileRecord(
            path=record.path,
            content_hash=record.content_hash,
            module=record.module,
            is_test=record.is_test,
            parse_error=record.parse_error,
            imports=record.imports,
            resolved_imports=tuple(resolved_imports),
        )
    return resolved


def _resolve_requests(
    requests: tuple[ImportRequest, ...],
    module_to_path: dict[str, str],
) -> set[str]:
    results: set[str] = set()
    for request in requests:
        if not request.module:
            continue
        if not request.is_from:
            target = _best_module_match(request.module, module_to_path)
            if target:
                results.add(target)
            continue
        if not request.names or request.names == ("*",):
            target = _best_module_match(request.module, module_to_path)
            if target:
                results.add(target)
            continue
        for name in request.names:
            target = _best_module_match(f"{request.module}.{name}", module_to_path)
            if target:
                results.add(target)
                continue
            fallback = _best_module_match(request.module, module_to_path)
            if fallback:
                results.add(fallback)
    return results


def _best_module_match(module_name: str, module_to_path: dict[str, str]) -> str | None:
    current = module_name
    while current:
        path = module_to_path.get(current)
        if path is not None:
            return path
        if "." not in current:
            break
        current = current.rsplit(".", 1)[0]
    return None


def _build_reverse_edges(
    files: dict[str, FileRecord],
    module_to_path: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    reverse_edges: dict[str, set[str]] = {path: set() for path in files}
    for importing_path, record in files.items():
        for imported_path in record.resolved_imports:
            if imported_path in reverse_edges:
                reverse_edges[imported_path].add(importing_path)
    return {path: tuple(sorted(importers)) for path, importers in reverse_edges.items()}
