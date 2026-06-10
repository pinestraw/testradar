from __future__ import annotations

from testradar.models import SelectionResult


def selection_report(result: SelectionResult) -> dict[str, object]:
    return {
        "full_suite": result.full_suite,
        "graph_mode": result.graph_mode,
        "reasons": result.reasons,
        "targets": [
            {
                "target": item.target,
                "source": item.source.value,
                "reason": item.reason,
            }
            for item in result.targets
        ],
    }
