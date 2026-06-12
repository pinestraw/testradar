from __future__ import annotations

from testradar.models import SelectionResult


def selection_report(result: SelectionResult) -> dict[str, object]:
    target_strings = result.target_strings()
    file_target_count = sum(1 for target in target_strings if "::" not in target)
    return {
        "full_suite": result.full_suite,
        "graph_mode": result.graph_mode,
        "resolved_base": result.resolved_base,
        "resolved_head": result.resolved_head,
        "comparison_mode": result.comparison_mode,
        "reasons": result.reasons,
        "reason_count": len(result.reasons),
        "escalations": result.escalations,
        "escalation_count": len(result.escalations),
        "target_count": len(target_strings),
        "file_target_count": file_target_count,
        "nodeid_target_count": len(target_strings) - file_target_count,
        "targets": [
            {
                "target": item.target,
                "source": item.source.value,
                "reason": item.reason,
            }
            for item in result.targets
        ],
    }
