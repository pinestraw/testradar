from __future__ import annotations

from pathlib import PurePosixPath

from testradar.models import ChangeScope, Classification, FileChange


def classify_django_change(change: FileChange) -> Classification | None:
    path = change.path
    comparison = change.comparison_path
    pure = PurePosixPath(path)
    comparison_pure = PurePosixPath(comparison)

    if pure.name.startswith("settings") and pure.suffix == ".py":
        return Classification(path=path, scope=ChangeScope.GLOBAL, reason="django-settings")
    if comparison_pure.name.startswith("settings") and comparison_pure.suffix == ".py":
        return Classification(path=path, scope=ChangeScope.GLOBAL, reason="django-settings")

    if pure.name == "manage.py" or comparison_pure.name == "manage.py":
        return Classification(path=path, scope=ChangeScope.GLOBAL, reason="django-manage")

    if "migrations" in pure.parts and path.endswith(".py"):
        anchor = _app_anchor(pure)
        if anchor:
            return Classification(path=path, scope=ChangeScope.APP, reason="django-migration", anchor=anchor)
    if "migrations" in comparison_pure.parts and comparison.endswith(".py"):
        anchor = _app_anchor(comparison_pure)
        if anchor:
            return Classification(
                path=path,
                scope=ChangeScope.APP,
                reason="django-migration",
                anchor=anchor,
                uses_old_graph=True,
            )

    if comparison.startswith("requirements/") or path.startswith("requirements/"):
        return Classification(path=path, scope=ChangeScope.GLOBAL, reason="django-requirements")

    return None


def _app_anchor(path: PurePosixPath) -> str | None:
    try:
        index = path.parts.index("migrations")
    except ValueError:
        return None
    if index == 0:
        return None
    return PurePosixPath(*path.parts[:index]).as_posix()
