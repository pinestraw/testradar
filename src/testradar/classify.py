from __future__ import annotations

from testradar.config import TestradarConfig
from testradar.models import Classification, FileChange
from testradar.policy.defaults import classify_change
from testradar.policy.presets.django import classify_django_change


def classify_changes(config: TestradarConfig, changes: list[FileChange]) -> list[Classification]:
    classifications: list[Classification] = []
    for change in changes:
        preset_decision = _classify_with_presets(config, change)
        if preset_decision is not None:
            classifications.append(preset_decision)
            continue
        classifications.append(classify_change(config, change))
    return classifications


def _classify_with_presets(
    config: TestradarConfig,
    change: FileChange,
) -> Classification | None:
    if "django" in config.presets:
        decision = classify_django_change(change)
        if decision is not None:
            return decision
    return None
