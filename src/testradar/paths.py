from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath


DEFAULT_IGNORED_PATH_PATTERNS = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".testradar",
    "node_modules",
    ".coverage*",
    ".testmondata*",
)


def path_is_ignored(path: str, ignored_path_patterns: tuple[str, ...]) -> bool:
    pure = PurePosixPath(path)
    return any(
        fnmatch(path, pattern)
        or fnmatch(pure.name, pattern)
        or any(fnmatch(part, pattern) for part in pure.parts)
        for pattern in ignored_path_patterns
    )
