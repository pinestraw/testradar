from __future__ import annotations

from pathlib import Path

from testradar.classify import classify_changes
from testradar.config import TestradarConfig
from testradar.gitdiff import changed_files, resolve_base_commit
from testradar.graph.build import update_graph_incremental
from testradar.graph.invert import all_test_files, app_tests, dependent_tests, tests_under
from testradar.graph.store import load_graph, save_graph
from testradar.models import (
    ChangeScope,
    GraphSnapshot,
    SelectedTarget,
    SelectionResult,
    SelectionSource,
)
from testradar.nodeids import select_changed_tests


SOURCE_PRIORITY = {
    SelectionSource.STATIC: 0,
    SelectionSource.DYNAMIC: 1,
    SelectionSource.GLOBAL: 2,
}


def index_repository(config: TestradarConfig) -> tuple[GraphSnapshot, str]:
    previous = load_graph(config.graph_path)
    snapshot, mode = update_graph_incremental(config, previous)
    save_graph(config.graph_path, snapshot)
    return snapshot, mode


def select_targets(config: TestradarConfig) -> SelectionResult:
    previous = load_graph(config.graph_path)
    base_commit = resolve_base_commit(config.repo_root, config.base_ref)
    changes = changed_files(config.repo_root, base_commit)
    current, graph_mode = update_graph_incremental(config, previous)
    save_graph(config.graph_path, current)

    targets: dict[str, SelectedTarget] = {}
    reasons: list[str] = []
    full_suite = False

    for change, classification in zip(changes, classify_changes(config, changes)):
        if classification.scope == ChangeScope.IGNORE:
            continue

        if classification.scope == ChangeScope.GLOBAL:
            full_suite = True
            reasons.append(f"{change.path}: {classification.reason}")
            _record_test_files(targets, all_test_files(current), SelectionSource.GLOBAL, classification.reason)
            continue

        if classification.scope == ChangeScope.TEST:
            if change.is_deleted:
                continue
            reasons.append(f"{change.path}: {classification.reason}")
            _record_test_files(
                targets,
                _select_test_change(config.repo_root / change.path, change),
                SelectionSource.STATIC,
                classification.reason,
            )
            continue

        if classification.scope == ChangeScope.SUBTREE:
            snapshot = previous if classification.uses_old_graph and previous is not None else current
            anchor = classification.anchor or ""
            reasons.append(f"{change.path}: {classification.reason} ({anchor})")
            _record_test_files(targets, tests_under(snapshot, anchor), SelectionSource.STATIC, classification.reason)
            continue

        if classification.scope == ChangeScope.APP:
            snapshot = previous if classification.uses_old_graph and previous is not None else current
            anchor = classification.anchor or ""
            reasons.append(f"{change.path}: {classification.reason} ({anchor})")
            _record_test_files(targets, app_tests(snapshot, anchor), SelectionSource.STATIC, classification.reason)
            continue

        if classification.scope == ChangeScope.SOURCE:
            reasons.append(f"{change.path}: {classification.reason}")
            _record_test_files(
                targets,
                _select_source_change(current=current, previous=previous, change=change),
                SelectionSource.STATIC,
                classification.reason,
            )
            continue

    return SelectionResult(
        targets=sorted(targets.values(), key=lambda item: item.target),
        reasons=reasons,
        graph_snapshot=current,
        full_suite=full_suite,
        graph_mode=graph_mode,
    )


def static_only_select(config: TestradarConfig) -> SelectionResult:
    return select_targets(config)


def _select_test_change(path: Path, change) -> list[str]:
    if change.is_added or change.is_rename or not change.hunks:
        return [change.path]
    try:
        return select_changed_tests(path, change.path, change.hunks)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return [change.path]


def _select_source_change(
    *,
    current: GraphSnapshot,
    previous: GraphSnapshot | None,
    change,
) -> set[str]:
    snapshot = current
    changed_path = change.path
    tests = set()

    if change.is_deleted and previous is not None and change.old_path:
        snapshot = previous
        changed_path = change.old_path
    elif change.is_rename and previous is not None and change.old_path:
        tests.update(dependent_tests(previous, change.old_path))

    record = snapshot.files.get(changed_path)
    if record and record.parse_error:
        return all_test_files(current)

    tests.update(dependent_tests(snapshot, changed_path))
    if change.is_rename:
        tests.update(dependent_tests(current, change.path))
    return tests


def _record_test_files(
    targets: dict[str, SelectedTarget],
    items,
    source: SelectionSource,
    reason: str,
) -> None:
    for item in items:
        _record_target(targets, item, source, reason)


def _record_target(
    targets: dict[str, SelectedTarget],
    target: str,
    source: SelectionSource,
    reason: str,
) -> None:
    existing = targets.get(target)
    if existing and SOURCE_PRIORITY[existing.source] >= SOURCE_PRIORITY[source]:
        return
    targets[target] = SelectedTarget(target=target, source=source, reason=reason)
