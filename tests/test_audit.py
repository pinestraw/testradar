from __future__ import annotations

import json

from testradar.audit import ProbeOutcome, calculate_miss_rate, load_node_set


def test_calculate_miss_rate_and_json_loader(tmp_path):
    payload = {
        "targets": [
            {"target": "tests/test_one.py"},
            {"target": "tests/test_two.py::test_case"},
        ],
    }
    path = tmp_path / "selected.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    selected = load_node_set(path)
    result = calculate_miss_rate(selected, {"tests/test_two.py::test_case", "tests/test_three.py"})

    assert selected == {"tests/test_one.py", "tests/test_two.py::test_case"}
    assert result.missed == {"tests/test_three.py"}
    assert result.miss_rate == 0.5


def test_probe_outcome_is_lightweight_contract():
    probe = ProbeOutcome(name="reverse-canary", passed=True, detail="static miss preserved")
    assert probe.name == "reverse-canary"
    assert probe.passed is True
