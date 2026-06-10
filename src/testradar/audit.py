from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from testradar.models import AuditResult, SelectionResult


class ProbeVerifier(Protocol):
    name: str

    def verify(self, result: SelectionResult) -> "ProbeOutcome":
        ...


@dataclass(frozen=True)
class ProbeOutcome:
    name: str
    passed: bool
    detail: str


def calculate_miss_rate(selected: set[str], failed: set[str]) -> AuditResult:
    return AuditResult(selected=selected, failed=failed, missed=failed - selected)


def load_node_set(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return set()
    if content.startswith("{") or content.startswith("["):
        payload = json.loads(content)
        if isinstance(payload, dict) and "targets" in payload:
            return {
                item["target"]
                for item in payload["targets"]
                if isinstance(item, dict) and isinstance(item.get("target"), str)
            }
        if isinstance(payload, list):
            return {item for item in payload if isinstance(item, str)}
        raise ValueError(f"Unsupported JSON payload in {path}")
    return {line.strip() for line in content.splitlines() if line.strip()}
