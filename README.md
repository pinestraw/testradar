# testradar

`testradar` is a framework-agnostic Python test-impact-analysis package.

It computes affected pytest targets from git changes without importing the code
under test, pytest, or any application framework. The static engine works from
AST parsing and git metadata, and can be configured for plain Python projects
or with an optional Django preset.

## Quick start

1. Install the package.
2. Add `[tool.testradar]` to `pyproject.toml`.
3. Run `testradar index`.
4. Run `testradar select` and feed the emitted targets to pytest.

## Status

This repository currently implements the static analysis engine, incremental
graph storage, CLI, pytest collection filter, a Django preset, and synthetic
tests. Dynamic coverage-context refinement is intentionally deferred until the
static-only savings are proven in a downstream consumer.
