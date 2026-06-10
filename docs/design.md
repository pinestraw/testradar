# Design

`testradar` is a static-first test impact analysis engine for pytest projects.

## Core constraints

- It never imports application code, pytest, Django, or the database to compute selection.
- It works from git diffs, AST parsing, and a persisted import graph.
- Every uncertain branch widens selection rather than narrowing it.

## Main pieces

- `testradar.graph.build`: parses Python files, records import requests, and resolves them against the current module map.
- `testradar.graph.store`: persists the graph with per-file hashes and a repo fingerprint.
- `testradar.gitdiff`: resolves the base commit and parses zero-context hunks.
- `testradar.select`: classifies file changes, updates the graph incrementally, and emits pytest targets.
- `testradar.pytest_plugin`: deselects collected pytest items from a target list.
- `testradar.detectors.pytest`: captures pytest plugin-string registrations such as `pytest_plugins = [...]`.

## Incremental model

`index` and `select` both load the stored graph, rescan repository hashes, and only reparse Python files whose content changed. Import resolution is then recomputed against the current module map so rename/add/remove events can be reflected without reparsing the whole tree.

If the graph store is missing or incompatible, `testradar` falls back to a full rebuild.

## Selection model

- Direct test-file edits try function-level selection first.
- Decorated or parametrized tests, module-level edits, parse failures, and rename ambiguity fall back to whole-file or wider selection.
- Source-file edits walk reverse import edges to dependent test files.
- When traversal reaches a `conftest.py`, selection expands to that `conftest` scope because pytest injects it without a normal import edge.
- Global policy matches select the full suite.

Dynamic coverage-context refinement is intentionally deferred. The current package is static-only by design.
