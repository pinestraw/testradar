from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from testradar.models import FileChange, HunkRange
from testradar.paths import DEFAULT_IGNORED_PATH_PATTERNS, path_is_ignored

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def resolve_base_commit(
    repo_root: Path,
    base_ref: str,
    *,
    git_dir: Optional[Path] = None,
    git_work_tree: Optional[Path] = None,
) -> str:
    result = _git(repo_root, "merge-base", base_ref, "HEAD", git_dir=git_dir, git_work_tree=git_work_tree)
    return result.stdout.strip()


def changed_files(
    repo_root: Path,
    base_commit: str,
    *,
    git_dir: Optional[Path] = None,
    git_work_tree: Optional[Path] = None,
    ignored_path_patterns: tuple[str, ...] = DEFAULT_IGNORED_PATH_PATTERNS,
) -> list[FileChange]:
    raw = _git(
        repo_root,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        base_commit,
        git_dir=git_dir,
        git_work_tree=git_work_tree,
    ).stdout
    changes = _parse_name_status(raw)
    tracked_paths = {change.path for change in changes}

    untracked = _git(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        git_dir=git_dir,
        git_work_tree=git_work_tree,
    ).stdout
    for raw_path in untracked.split("\0"):
        if not raw_path:
            continue
        if _is_ignored_path(raw_path, ignored_path_patterns=ignored_path_patterns):
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
            _change_with_hunks(
                repo_root,
                base_commit,
                change,
                git_dir=git_dir,
                git_work_tree=git_work_tree,
            )
            for change in changes
        ),
        key=lambda item: (item.path, item.status, item.old_path or ""),
    )


def _attach_hunks(
    repo_root: Path,
    base_commit: str,
    change: FileChange,
    *,
    git_dir: Optional[Path] = None,
    git_work_tree: Optional[Path] = None,
) -> FileChange:
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
        git_dir=git_dir,
        git_work_tree=git_work_tree,
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


def _change_with_hunks(
    repo_root: Path,
    base_commit: str,
    change: FileChange,
    *,
    git_dir: Optional[Path] = None,
    git_work_tree: Optional[Path] = None,
) -> FileChange:
    if change.is_untracked:
        return change
    return _attach_hunks(
        repo_root,
        base_commit,
        change,
        git_dir=git_dir,
        git_work_tree=git_work_tree,
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


def _is_ignored_path(path: str, *, ignored_path_patterns: tuple[str, ...] = DEFAULT_IGNORED_PATH_PATTERNS) -> bool:
    return path_is_ignored(path, ignored_path_patterns)


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


def _git(
    repo_root: Path,
    *args: str,
    git_dir: Optional[Path] = None,
    git_work_tree: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if git_dir is not None or git_work_tree is not None:
        env = os.environ.copy()
        if git_dir is not None:
            env["GIT_DIR"] = str(git_dir)
        if git_work_tree is not None:
            env["GIT_WORK_TREE"] = str(git_work_tree)
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        linked_message = _linked_worktree_hint(repo_root, git_dir=git_dir, git_work_tree=git_work_tree, error=exc)
        if linked_message is not None:
            raise RuntimeError(linked_message) from exc
        raise


def _linked_worktree_hint(
    repo_root: Path,
    *,
    git_dir: Optional[Path],
    git_work_tree: Optional[Path],
    error: subprocess.CalledProcessError,
) -> Optional[str]:
    if git_dir is not None and git_work_tree is not None:
        return None
    stderr = (error.stderr or "").strip()
    git_file = repo_root / ".git"
    if not git_file.is_file():
        return None
    gitdir_line = git_file.read_text(encoding="utf-8").strip()
    if not gitdir_line.startswith("gitdir: "):
        return None
    gitdir_path = Path(gitdir_line.removeprefix("gitdir: ").strip())
    if gitdir_path.exists():
        return None
    if "not a git repository" not in stderr:
        return None
    return (
        "testradar could not access git metadata for a linked worktree. "
        "This usually means the worktree checkout was bind-mounted without its shared git dir. "
        "Mount the common git directory and pass --git-dir / --git-work-tree "
        "(or set TESTRADAR_GIT_DIR / TESTRADAR_GIT_WORK_TREE). "
        f"repo_root={repo_root} missing_gitdir={gitdir_path}"
    )
