from __future__ import annotations

from testradar.policy.defaults import _matches_any, classify_change, is_test_path
from testradar.policy.presets.django import _app_anchor, classify_django_change
from testradar.models import ChangeScope, FileChange


def test_default_policy_identifies_test_and_support_paths(repo):
    config = repo.config()

    assert is_test_path(config, "tests/test_service.py") is True
    assert is_test_path(config, "tests/helpers.py") is False
    assert is_test_path(config, "tests/conftest.py") is False
    assert is_test_path(config, "pkg/__init__.py") is False
    assert is_test_path(config, "notes.txt") is False


def test_default_policy_classifies_global_lockfile_conftest_source_and_ignore(repo):
    config = repo.config()

    assert classify_change(config, FileChange(status="M", path="pyproject.toml")).scope == ChangeScope.GLOBAL
    assert classify_change(config, FileChange(status="M", path="docs/file.md", old_path="requirements.txt")).reason == "lockfile-policy"
    assert classify_change(config, FileChange(status="M", path="conftest.py")).reason == "root-conftest"
    subtree = classify_change(config, FileChange(status="M", path="tests/sub/conftest.py"))
    assert subtree.scope == ChangeScope.SUBTREE
    assert subtree.anchor == "tests/sub"
    assert classify_change(config, FileChange(status="M", path="tests/test_service.py")).scope == ChangeScope.TEST
    assert classify_change(config, FileChange(status="M", path="pkg/service.py")).scope == ChangeScope.SOURCE
    assert classify_change(config, FileChange(status="M", path="README.md")).scope == ChangeScope.IGNORE
    assert _matches_any("pkg/project.toml", ("project.toml",)) is True


def test_django_policy_covers_settings_manage_migrations_requirements_and_none():
    assert classify_django_change(FileChange(status="M", path="project/settings.py")).reason == "django-settings"
    assert classify_django_change(FileChange(status="M", path="x.py", old_path="project/settings_local.py")).reason == "django-settings"
    assert classify_django_change(FileChange(status="M", path="manage.py")).reason == "django-manage"

    migration = classify_django_change(FileChange(status="M", path="billing/migrations/0001_initial.py"))
    assert migration.scope == ChangeScope.APP
    assert migration.anchor == "billing"

    old_migration = classify_django_change(
        FileChange(status="R", path="renamed.py", old_path="billing/migrations/0001_initial.py"),
    )
    assert old_migration.uses_old_graph is True

    assert classify_django_change(FileChange(status="M", path="requirements/testing.txt")).reason == "django-requirements"
    assert classify_django_change(FileChange(status="M", path="pkg/service.py")) is None
    assert _app_anchor(type("P", (), {"parts": ("migrations", "0001.py"), "as_posix": lambda self: "migrations/0001.py"})()) is None
    assert _app_anchor(type("P", (), {"parts": ("billing", "migrations", "0001.py"), "as_posix": lambda self: "billing/migrations/0001.py"})()) == "billing"
