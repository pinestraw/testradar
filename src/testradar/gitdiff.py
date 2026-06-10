from __future__ import annotations

import re
import subprocess
from pathlib import Path

from testradar.models import FileChange, HunkRange

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
IGNORED_PATH_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".testradar",
    "__pycache__",
}


def resolve_base_commit(repo_root: Path, base_ref: str) -> str:
    result = _git(repo_root, "merge-base", base_ref, "HEAD")
    return result.stdout.strip()


def changed_files(repo_root: Path, base_commit: str) -> list[FileChange]:
    raw = _git(repo_root, "diff", "--name-status", "-z", "--find-renames", base_commit).stdout
    changes = _parse_name_status(raw)
    tracked_paths = {change.path for change in changes}

    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    for raw_path in untracked.split("\0"):
        if not raw_path:
            continue
        if _is_ignored_path(raw_path):
            continue
        if raw_path in tracked_paths:
            continue
        changes.append(
            FileChange(
                status="A",
                path=raw_path,
                hunks=_whole_file_hunks(repo_root / raw_path),
                is_untracked=True,
            ),
        )

    return sorted(
        (
            _attach_hunks(repo_root, base_commit, change)
            if not change.is_untracked
            else change
            for change in changes
        ),
        key=lambda item: (item.path, item.status, item.old_path or ""),
    )


def _attach_hunks(repo_root: Path, base_commit: str, change: FileChange) -> FileChange:
    diff_path = change.old_path if change.is_deleted else change.path
    diff_text = _git(
        repo_root,
        "diff",
        "-U0",
        "--no-color",
        "--find-renames",
        base_commit,
        "--",
        diff_path,
    ).stdout
    hunks = parse_hunks(diff_text)
    if change.is_rename and not hunks:
        hunks = _whole_file_hunks(repo_root / change.path)
    if change.is_added and not hunks:
        hunks = _whole_file_hunks(repo_root / change.path)
    return FileChange(
        status=change.status,
        path=change.path,
        old_path=change.old_path,
        hunks=hunks,
        is_untracked=change.is_untracked,
    )


def parse_hunks(diff_text: str) -> tuple[HunkRange, ...]:
    hunks: list[HunkRange] = []
    for line in diff_text.splitlines():
        match = HUNK_RE.match(line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        hunks.append(HunkRange(start=start, count=count))
    return tuple(hunks)


def _whole_file_hunks(path: Path) -> tuple[HunkRange, ...]:
    if not path.exists():
        return ()
    line_count = max(path.read_text(encoding="utf-8").count("\n") + 1, 1)
    return (HunkRange(start=1, count=line_count),)


def _is_ignored_path(path: str) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in Path(path).parts)


def _parse_name_status(raw: str) -> list[FileChange]:
    parts = raw.split("\0")
    changes: list[FileChange] = []
    index = 0
    while index < len(parts):
        status = parts[index]
        index += 1
        if not status:
            continue
        code = status[0]
        if code == "R":
            old_path = parts[index]
            new_path = parts[index + 1]
            index += 2
            changes.append(FileChange(status="R", path=new_path, old_path=old_path))
            continue
        if code == "C":
            _old_path = parts[index]
            new_path = parts[index + 1]
            index += 2
            changes.append(FileChange(status="A", path=new_path))
            continue
        path = parts[index]
        index += 1
        changes.append(FileChange(status=code, path=path))
    return changes


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
