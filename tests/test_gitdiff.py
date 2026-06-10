from __future__ import annotations

from testradar.gitdiff import parse_hunks


def test_parse_hunks_handles_zero_context_ranges():
    hunks = parse_hunks(
        """
@@ -4,2 +4,1 @@
@@ -12 +14,0 @@
@@ -20,0 +21,4 @@
""".strip(),
    )

    assert [(item.start, item.count) for item in hunks] == [(4, 1), (14, 0), (21, 4)]
