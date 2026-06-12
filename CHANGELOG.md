# Changelog

## 0.2.2 - 2026-06-11

- make legacy `except Foo, Bar:` sanitization work across Python 3.9 through 3.13 instead of depending on version-specific `SyntaxError` text
- make release/parse tests version-neutral where interpreter error wording differs

## 0.2.1 - 2026-06-11

- fix Python 3.9 and 3.10 release-metadata tests by using the packaged `tomli` fallback instead of importing `tomllib` unconditionally

## 0.2.0 - 2026-06-11

- add explicit `--diff-base` and `--diff-head` support with three-dot merge-base semantics for CI and promotion diffs
- add generic `--on-unclassified={ignore,full-suite,fail}` handling so callers can choose fail-open or fail-closed behavior without repo-specific rules
- include `resolved_base`, `resolved_head`, and `comparison_mode` in the JSON selection report
- expand test coverage and documentation for range resolution, worktrees, and fail-closed promotion usage

## 0.1.0 - 2026-06-10

- initial standalone packaging, CI, release automation, and static-first pytest target selection
