from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from testradar.gitdiff import (
    _attach_hunks,
    _git,
    _is_ignored_path,
    _parse_name_status,
    _whole_file_hunks,
    changed_files,
)
from testradar.models import FileChange, HunkRange


def test_parse_name_status_handles_copy_rename_and_standard_entries():
    changes = _parse_name_status("R100\0old.py\0new.py\0C100\0src.py\0copy.py\0M\0mod.py\0")

    assert [(item.status, item.path, item.old_path) for item in changes] == [
        ("R", "new.py", "old.py"),
        ("A", "copy.py", None),
        ("M", "mod.py", None),
    ]


def test_whole_file_hunks_and_ignored_path(tmp_path):
    path = tmp_path / "file.py"
    path.write_text("one\ntwo\n", encoding="utf-8")

    assert _whole_file_hunks(path) == (HunkRange(start=1, count=3),)
    assert _whole_file_hunks(tmp_path / "missing.py") == ()
    assert _is_ignored_path(".testradar/cache.msgpack") is True
    assert _is_ignored_path("reports/selection.json", ignored_path_patterns=("reports/*",)) is True
    assert _is_ignored_path("src/app.py") is False


def test_attach_hunks_falls_back_for_rename_and_add(monkeypatch, tmp_path):
    target = tmp_path / "renamed.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr("testradar.gitdiff._git", lambda *args, **kwargs: SimpleNamespace(stdout=""))

    renamed = _attach_hunks(
        tmp_path,
        "base",
        FileChange(status="R", path="renamed.py", old_path="old.py"),
    )
    added = _attach_hunks(
        tmp_path,
        "base",
        FileChange(status="A", path="renamed.py"),
    )

    assert renamed.hunks == (HunkRange(start=1, count=2),)
    assert added.hunks == (HunkRange(start=1, count=2),)


def test_changed_files_handles_duplicate_tracked_and_untracked(monkeypatch, tmp_path):
    tracked = tmp_path / "tracked.py"
    tracked.write_text("VALUE = 1\n", encoding="utf-8")
    new_file = tmp_path / "new.py"
    new_file.write_text("VALUE = 2\n", encoding="utf-8")

    def fake_git(_repo_root, *args, **_kwargs):
        if args[:2] == ("diff", "--name-status"):
            return SimpleNamespace(stdout="M\0tracked.py\0")
        if args[:2] == ("ls-files", "--others"):
            return SimpleNamespace(stdout="tracked.py\0new.py\0.testradar/cache.py\0")
        if args[:2] == ("diff", "-U0"):
            return SimpleNamespace(stdout="@@ -1 +1 @@")
        raise AssertionError(args)

    monkeypatch.setattr("testradar.gitdiff._git", fake_git)

    changes = changed_files(tmp_path, "base", ignored_path_patterns=("new.py", ".testradar"))

    assert [(item.status, item.path, item.is_untracked) for item in changes] == [("M", "tracked.py", False)]


def test_git_passes_explicit_git_env(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs["cwd"]
        captured["env"] = kwargs["env"]
        return SimpleNamespace(stdout="")

    monkeypatch.setattr("subprocess.run", fake_run)

    _git(
        tmp_path,
        "status",
        git_dir=tmp_path / ".git/worktrees/feature",
        git_work_tree=tmp_path,
    )

    assert captured["cmd"] == ["git", "status"]
    assert captured["cwd"] == tmp_path
    assert captured["env"]["GIT_DIR"].endswith(".git/worktrees/feature")
    assert captured["env"]["GIT_WORK_TREE"] == str(tmp_path)


def test_git_raises_linked_worktree_hint_for_missing_gitdir(monkeypatch, tmp_path):
    (tmp_path / ".git").write_text(
        "gitdir: /missing/common/.git/worktrees/feature\n",
        encoding="utf-8",
    )

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            128,
            ["git", "merge-base", "origin/main", "HEAD"],
            stderr="fatal: not a git repository: /missing/common/.git/worktrees/feature",
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="linked worktree"):
        _git(tmp_path, "merge-base", "origin/main", "HEAD")
