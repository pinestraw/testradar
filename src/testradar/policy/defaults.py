from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath

from testradar.config import TestradarConfig
from testradar.models import ChangeScope, Classification, FileChange


def is_test_path(config: TestradarConfig, path: str) -> bool:
    pure = PurePosixPath(path)
    if pure.suffix != ".py":
        return False
    if pure.name in {"conftest.py", "__init__.py"}:
        return False
    return any(fnmatch(pure.name, pattern) for pattern in config.test_file_patterns)


def classify_change(config: TestradarConfig, change: FileChange) -> Classification:
    relative = change.path
    comparison = change.comparison_path
    if _matches_any(relative, config.global_patterns) or _matches_any(comparison, config.global_patterns):
        return Classification(path=relative, scope=ChangeScope.GLOBAL, reason="global-policy")
    if _matches_any(relative, config.lockfile_patterns) or _matches_any(comparison, config.lockfile_patterns):
        return Classification(path=relative, scope=ChangeScope.GLOBAL, reason="lockfile-policy")

    if relative.endswith("/conftest.py") or relative == "conftest.py":
        anchor = PurePosixPath(relative).parent.as_posix()
        if anchor == ".":
            return Classification(path=relative, scope=ChangeScope.GLOBAL, reason="root-conftest")
        return Classification(path=relative, scope=ChangeScope.SUBTREE, reason="conftest-subtree", anchor=anchor)

    if comparison.endswith(".py") and is_test_path(config, comparison):
        return Classification(path=relative, scope=ChangeScope.TEST, reason="test-file")
    if relative.endswith(".py"):
        return Classification(path=relative, scope=ChangeScope.SOURCE, reason="python-source")

    return Classification(path=relative, scope=ChangeScope.IGNORE, reason="no-policy-match")


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    pure = PurePosixPath(path)
    return any(fnmatch(path, pattern) or fnmatch(pure.name, pattern) for pattern in patterns)
