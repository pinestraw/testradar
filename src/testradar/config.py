from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Any, Optional

from testradar.paths import DEFAULT_IGNORED_PATH_PATTERNS

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


DEFAULT_GRAPH_PATH = ".testradar/graph.msgpack"
DEFAULT_TEST_FILE_PATTERNS = ("tests.py", "test_*.py", "*_test.py", "*_tests.py")
DEFAULT_LOCKFILE_PATTERNS = (
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "pdm.lock",
    "requirements*.txt",
)
DEFAULT_GLOBAL_PATTERNS = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "tox.ini",
)


@dataclass(frozen=True)
class TestradarConfig:
    repo_root: Path
    base_ref: str
    source_roots: tuple[Path, ...]
    graph_path: Path
    git_dir: Optional[Path]
    git_work_tree: Optional[Path]
    presets: tuple[str, ...]
    detector_paths: tuple[str, ...]
    test_file_patterns: tuple[str, ...]
    lockfile_patterns: tuple[str, ...]
    global_patterns: tuple[str, ...]
    ignored_path_patterns: tuple[str, ...]

    def normalized_source_roots(self) -> tuple[str, ...]:
        return tuple(path.relative_to(self.repo_root).as_posix() for path in self.source_roots)


def _load_table(pyproject_path: Path) -> dict[str, Any]:
    if not pyproject_path.exists():
        return {}
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    tool = data.get("tool", {})
    raw = tool.get("testradar", {})
    if not isinstance(raw, dict):
        raise ValueError("[tool.testradar] must be a table")
    return raw


def _ensure_tuple(raw: Any, *, field_name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(raw)
    raise ValueError(f"{field_name} must be a string or list of strings")


def _resolve_optional_path(repo_root: Path, raw: Any, *, field_name: str) -> Optional[Path]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{field_name} must be a string")
    resolved = Path(raw)
    if not resolved.is_absolute():
        resolved = (repo_root / resolved).resolve()
    return resolved


def _merge_unique(base: tuple[str, ...], extra: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(base)
    for item in extra:
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def load_config(
    repo_root: Path,
    *,
    base_ref: Optional[str] = None,
    graph_path: Optional[str] = None,
    git_dir: Optional[str] = None,
    git_work_tree: Optional[str] = None,
) -> TestradarConfig:
    pyproject_table = _load_table(repo_root / "pyproject.toml")

    raw_presets = _ensure_tuple(pyproject_table.get("presets"), field_name="presets")
    preset = pyproject_table.get("preset")
    if preset is not None:
        raw_presets = raw_presets + _ensure_tuple(preset, field_name="preset")

    configured_roots = _ensure_tuple(pyproject_table.get("source_roots"), field_name="source_roots")
    if not configured_roots:
        configured_roots = (".",)
    source_roots = tuple((repo_root / root).resolve() for root in configured_roots)

    resolved_graph_path = Path(
        graph_path or pyproject_table.get("graph_path") or DEFAULT_GRAPH_PATH,
    )
    if not resolved_graph_path.is_absolute():
        resolved_graph_path = (repo_root / resolved_graph_path).resolve()

    return TestradarConfig(
        repo_root=repo_root.resolve(),
        base_ref=base_ref or pyproject_table.get("base_ref", "origin/main"),
        source_roots=source_roots,
        graph_path=resolved_graph_path,
        git_dir=_resolve_optional_path(
            repo_root,
            git_dir or pyproject_table.get("git_dir") or environ.get("TESTRADAR_GIT_DIR"),
            field_name="git_dir",
        ),
        git_work_tree=_resolve_optional_path(
            repo_root,
            git_work_tree
            or pyproject_table.get("git_work_tree")
            or environ.get("TESTRADAR_GIT_WORK_TREE"),
            field_name="git_work_tree",
        ),
        presets=raw_presets,
        detector_paths=_ensure_tuple(pyproject_table.get("detectors"), field_name="detectors"),
        test_file_patterns=_ensure_tuple(
            pyproject_table.get("test_file_patterns"),
            field_name="test_file_patterns",
        )
        or DEFAULT_TEST_FILE_PATTERNS,
        lockfile_patterns=_ensure_tuple(
            pyproject_table.get("lockfile_patterns"),
            field_name="lockfile_patterns",
        )
        or DEFAULT_LOCKFILE_PATTERNS,
        global_patterns=_ensure_tuple(pyproject_table.get("global_patterns"), field_name="global_patterns")
        or DEFAULT_GLOBAL_PATTERNS,
        ignored_path_patterns=_merge_unique(
            DEFAULT_IGNORED_PATH_PATTERNS,
            _ensure_tuple(
                pyproject_table.get("ignored_path_patterns"),
                field_name="ignored_path_patterns",
            ),
        ),
    )
