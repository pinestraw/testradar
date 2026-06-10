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

Example with persisted outputs:

```bash
testradar select \
  --report reports/testradar-selection.json \
  --targets-file reports/testradar-targets.txt
```

### Linked worktrees in Docker

If you run `testradar` inside a container against a linked git worktree, mount the
shared git directory and pass `--git-dir` plus `--git-work-tree`. Example:

```bash
testradar \
  --repo-root /code \
  --git-dir /git-common/worktrees/my-worktree \
  --git-work-tree /code \
  select
```

### Ignoring runner artifacts

`testradar` ignores common cache and coverage artifacts by default. Repositories
with additional long-lived generated paths can extend this in `pyproject.toml`:

```toml
[tool.testradar]
ignored_path_patterns = ["coverage", "reports/*", "web/.next/*"]
```

## Status

This repository currently implements the static analysis engine, incremental
graph storage, CLI, pytest collection filter, a Django preset, and synthetic
tests. Dynamic coverage-context refinement is intentionally deferred until the
static-only savings are proven in a downstream consumer.
