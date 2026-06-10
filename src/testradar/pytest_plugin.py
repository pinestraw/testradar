from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--testradar",
        action="store",
        default=None,
        help="Path to a newline-delimited list of pytest targets emitted by testradar.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    selected_path = config.getoption("--testradar")
    if not selected_path:
        return
    path = Path(selected_path)
    targets = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if not targets:
        return

    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if any(_matches_target(item.nodeid, target) for target in targets):
            kept.append(item)
        else:
            deselected.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


def _matches_target(nodeid: str, target: str) -> bool:
    if "::" in target:
        return nodeid == target or nodeid.startswith(f"{target}[")
    return nodeid == target or nodeid.startswith(f"{target}::")
