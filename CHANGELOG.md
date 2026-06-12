# Changelog

## 0.2.0 - 2026-06-11

- add explicit `--diff-base` and `--diff-head` support with three-dot merge-base semantics for CI and promotion diffs
- add generic `--on-unclassified={ignore,full-suite,fail}` handling so callers can choose fail-open or fail-closed behavior without repo-specific rules
- include `resolved_base`, `resolved_head`, and `comparison_mode` in the JSON selection report
- expand test coverage and documentation for range resolution, worktrees, and fail-closed promotion usage

## 0.1.0 - 2026-06-10

- initial standalone packaging, CI, release automation, and static-first pytest target selection
