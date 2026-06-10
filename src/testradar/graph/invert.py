from __future__ import annotations

from collections import deque
from pathlib import PurePosixPath

from testradar.models import GraphSnapshot


def dependent_tests(snapshot: GraphSnapshot, changed_path: str) -> set[str]:
    if changed_path not in snapshot.files:
        return set()

    queue = deque([changed_path])
    visited = {changed_path}
    tests: set[str] = set()

    while queue:
        current = queue.popleft()
        record = snapshot.files.get(current)
        if record and record.is_test:
            tests.add(current)
        if _is_conftest_path(current):
            tests.update(_tests_for_conftest(snapshot, current))
        for importer in snapshot.reverse_edges.get(current, ()):
            if importer not in visited:
                visited.add(importer)
                queue.append(importer)

    return tests


def all_test_files(snapshot: GraphSnapshot) -> set[str]:
    return {path for path, record in snapshot.files.items() if record.is_test}


def tests_under(snapshot: GraphSnapshot, anchor: str) -> set[str]:
    normalized = anchor.rstrip("/")
    prefix = f"{normalized}/"
    return {
        path
        for path, record in snapshot.files.items()
        if record.is_test and (path == normalized or path.startswith(prefix))
    }


def app_tests(snapshot: GraphSnapshot, anchor: str) -> set[str]:
    app_name = anchor.rstrip("/").split("/")[-1]
    tests = tests_under(snapshot, anchor)
    tests.update(
        path
        for path, record in snapshot.files.items()
        if record.is_test and (path.startswith(f"tests/{app_name}/") or f"/{app_name}/" in path)
    )
    return tests


def _is_conftest_path(path: str) -> bool:
    return PurePosixPath(path).name == "conftest.py"


def _tests_for_conftest(snapshot: GraphSnapshot, path: str) -> set[str]:
    anchor = PurePosixPath(path).parent.as_posix()
    if anchor == ".":
        return all_test_files(snapshot)
    return tests_under(snapshot, anchor)
