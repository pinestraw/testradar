# testradar

`testradar` is a static-first, framework-agnostic test impact analysis tool for
pytest projects.

It computes affected pytest targets from git changes without importing your
application, booting Django, touching a database, or collecting runtime
coverage. It builds a persisted import graph from Python ASTs, compares the
current checkout to a git base ref, and emits the smallest safe pytest subset it
can justify. When it cannot safely narrow, it widens selection instead of
guessing.

`testradar` currently powers targeted test selection in a downstream production
deploy pipeline. The package is not published to PyPI yet, so the installation
instructions below use a local checkout or a direct GitHub install. The release
automation is now wired so a tagged `main` release can publish to TestPyPI,
PyPI, and GitHub Releases once the one-time Trusted Publisher setup is done.

## What it does

- Builds and incrementally updates a persisted Python import graph.
- Classifies git changes into test-file, source-file, app-scoped, subtree, or
  full-suite triggers.
- Selects file targets or pytest nodeids, depending on what can be narrowed
  safely.
- Supports plain Python repositories out of the box.
- Ships an optional Django preset for settings, migrations, and common Django
  model-coupling patterns.
- Works in normal clones, linked worktrees, and Dockerized CI.

## What it does not do

- It does not import application code to compute selection.
- It does not need pytest collection to compute selection.
- It does not promise the mathematically smallest subset.
- It does not narrow below the static dependency floor when the diff is
  ambiguous.

That tradeoff is deliberate: predictable safety over aggressive under-selection.

## Requirements

- Python `3.9+`
- `git`
- A repository tracked in Git
- A pytest-based test suite

## Installation

### Install from a local checkout

This is the recommended path while the package is still unpublished.

```bash
git clone git@github.com:pinestraw/testradar.git
cd testradar
make bootstrap
```

For local development:

```bash
make bootstrap-dev
```

For coverage helpers:

```bash
./scripts/pip_user_install.sh "$(./scripts/find_python.sh)" -e '.[cov]'
```

### Install directly from GitHub

```bash
pip install "git+https://github.com/pinestraw/testradar.git"
```

The helper scripts install into user site-packages rather than a virtualenv. If
your user-site bin directory is not on `PATH`, invoke the CLI as
`python -m testradar`.

### Future PyPI install

Once the project is published, the install will become:

```bash
pip install testradar
```

## Quick start

### 1. Add config to `pyproject.toml`

Minimal config:

```toml
[tool.testradar]
base_ref = "origin/main"
source_roots = ["."]
graph_path = ".testradar/graph.msgpack"
```

Typical Django config:

```toml
[tool.testradar]
base_ref = "origin/staging"
source_roots = ["."]
graph_path = ".testradar/graph.msgpack"
preset = "django"
ignored_path_patterns = ["coverage", "reports/*", "web/.next/*"]
```

### 2. Warm the graph

```bash
testradar index
```

This is optional in the sense that `testradar select` can build the graph on
demand. It is still useful as a warm-up step in CI, local benchmarking, and
debugging.

### 3. Inspect how the diff was classified

```bash
testradar classify --json
```

This is the fastest way to understand why a change widened to an app scope,
subtree, or full suite.

### 4. Emit selected pytest targets

```bash
testradar select \
  --report reports/testradar-selection.json \
  --targets-file reports/testradar-targets.txt
```

By default, `select` prints newline-delimited pytest targets to stdout. The
optional `--report` file writes a machine-readable JSON summary, and
`--targets-file` writes the selected targets to disk.

### 5. Run pytest against the selected subset

You have two practical integration modes.

#### Mode A: pass emitted targets directly to pytest

```bash
pytest $(testradar select)
```

This is simple and fast when your shell wrapper is straightforward and you are
happy to pass file paths and nodeids directly as command-line arguments.

#### Mode B: collect normally, then deselect with the pytest plugin

```bash
testradar select --targets-file .testradar/targets.txt
pytest -p testradar.pytest_plugin --testradar .testradar/targets.txt
```

This mode is usually easier to integrate with:

- existing pytest wrappers
- sharding layers such as `pytest-split`
- scripts that already control the pytest argument list
- cases where you want a persisted target manifest

The plugin accepts both file targets like `tests/test_api.py` and nodeids like
`tests/test_api.py::test_happy_path`.

## Common workflows

### Local developer loop

```bash
testradar index
testradar classify
testradar select --targets-file .testradar/targets.txt
pytest -p testradar.pytest_plugin --testradar .testradar/targets.txt
```

### CI or deploy gating

```bash
testradar \
  --repo-root "$PWD" \
  --base-ref origin/staging \
  select \
  --report reports/testradar-selection.json \
  --targets-file reports/testradar-targets.txt

pytest -p testradar.pytest_plugin --testradar reports/testradar-targets.txt
```

### Audit how often selection misses failures

```bash
testradar audit \
  --selected reports/selected.txt \
  --failed reports/failed.txt
```

This emits JSON with:

- `selected`
- `failed`
- `missed`
- `miss_rate`

## Command reference

### `testradar index`

Builds or refreshes the persisted static graph.

Example output:

```json
{"graph_mode": "incremental", "python_files": 842}
```

### `testradar refresh`

Alias for `index` in the current static-only model.

### `testradar classify`

Shows how each changed file was interpreted.

Plain output:

```bash
testradar classify
```

JSON output:

```bash
testradar classify --json
```

Useful fields include:

- `path`
- `scope`
- `reason`
- `anchor`
- `status`
- `old_path`

### `testradar select`

Computes the selected pytest targets and optionally writes:

- newline-delimited targets via `--targets-file`
- a JSON report via `--report`
- a JSON rendering to stdout via `--json`

Example:

```bash
testradar select \
  --json \
  --report reports/selection.json \
  --targets-file reports/targets.txt
```

The JSON report includes fields such as:

- `target_count`
- `file_target_count`
- `nodeid_target_count`
- `full_suite`
- `graph_mode`
- `reason_count`
- `escalation_count`

### `testradar audit`

Compares a selected set to a failed set and reports the miss rate.

```bash
testradar audit --selected selected.txt --failed failed.txt
```

## Configuration reference

`testradar` reads `[tool.testradar]` from `pyproject.toml`.

### Core fields

- `base_ref`
  Default: `"origin/main"`
  Git ref used to compute the diff base.

- `source_roots`
  Default: `["."]`
  Roots scanned for Python source and tests.

- `graph_path`
  Default: `".testradar/graph.msgpack"`
  Where the persisted graph is stored.

### Policy fields

- `preset` or `presets`
  Enables preset policy packs such as `"django"`.

- `detectors`
  Import-path strings for extra coupling detectors.

- `test_file_patterns`
  Override the filename patterns treated as runnable pytest files.

- `lockfile_patterns`
  Override patterns that widen to the full suite when packaging inputs change.

- `global_patterns`
  Override patterns that are always treated as global/full-suite triggers.

- `ignored_path_patterns`
  Extra generated or irrelevant paths to ignore beyond the built-in defaults.

### Git/worktree override fields

- `git_dir`
- `git_work_tree`

These can be set in `pyproject.toml`, on the CLI, or through:

- `TESTRADAR_GIT_DIR`
- `TESTRADAR_GIT_WORK_TREE`

They matter most when the working tree and the shared Git metadata are mounted at
different paths, such as linked worktrees running inside a container.

## Linked worktrees and Docker

If you run `testradar` inside a container against a linked Git worktree, mount
the shared Git directory and pass both `--git-dir` and `--git-work-tree`.

Example:

```bash
testradar \
  --repo-root /code \
  --git-dir /git-common/worktrees/my-worktree \
  --git-work-tree /code \
  --base-ref origin/staging \
  select
```

Equivalent environment variables:

```bash
export TESTRADAR_GIT_DIR=/git-common/worktrees/my-worktree
export TESTRADAR_GIT_WORK_TREE=/code
testradar --repo-root /code select
```

Use this mode when:

- `.git` inside the container is a file that points outside the mount
- your CI runner mounts only the worktree contents
- you use Git linked worktrees heavily and want stable selection inside Docker

## Selection behavior

Some important default rules:

- Repo-root `conftest.py` selects the full suite.
- Nested `conftest.py` selects tests in that subtree.
- Packaging and lockfile changes widen to the full suite.
- Direct test-file edits try function-level selection first.
- Decorated or parametrized tests fall back to the whole file.
- Source-file edits walk reverse import edges to dependent tests.
- Parse failures and rename ambiguity widen selection instead of narrowing.
- `pytest_plugins = [...]` string registrations are treated as dependency edges.

For the detailed policy contract, see
[docs/policy.md](https://github.com/pinestraw/testradar/blob/main/docs/policy.md).

## Django preset

Enable it with:

```toml
[tool.testradar]
preset = "django"
```

The Django preset adds logic for:

- `settings*.py` and `manage.py` as full-suite triggers
- `requirements/` changes as full-suite triggers
- `migrations/*.py` as app-scoped selectors
- common Django model-coupling patterns such as `apps.get_model(...)`
- signal sender coupling such as `@receiver(..., sender="app.Model")`

More detail:
[docs/presets.md](https://github.com/pinestraw/testradar/blob/main/docs/presets.md)

## Troubleshooting

### `select` widened to the full suite

Run:

```bash
testradar classify --json
testradar select --json
```

Typical reasons:

- repo-root `conftest.py` changed
- `pyproject.toml` or lockfiles changed
- a parse failure forced safe widening
- a preset rule marked the change as global

### `select` seems slower than expected

The first run may rebuild the graph. After that, `index` and `select` are
incremental and only reparse files whose contents changed.

### Containerized worktree runs cannot resolve Git metadata

Set `--git-dir` and `--git-work-tree`, or the matching `TESTRADAR_*`
environment variables.

### Generated artifacts are polluting the diff

Extend `ignored_path_patterns`:

```toml
[tool.testradar]
ignored_path_patterns = ["coverage", "reports/*", "web/.next/*"]
```

### I want the narrowest possible runtime behavior

Use the plugin-based path and inspect the report JSON. It is easier to debug than
trying to infer what was passed to pytest from shell expansion alone.

## Development

Install dev dependencies:

```bash
make bootstrap-dev
```

Run the test suite:

```bash
make test
```

Build and validate release artifacts:

```bash
make release-check
```

Run Ruff:

```bash
ruff check .
ruff format --check .
```

The repository enforces `95%` minimum coverage on its own test suite via pytest
defaults in `pyproject.toml`.

## Deeper docs

- [Integration Guide](https://github.com/pinestraw/testradar/blob/main/docs/integration-guide.md)
- [Releasing](https://github.com/pinestraw/testradar/blob/main/docs/releasing.md)
- [Policy](https://github.com/pinestraw/testradar/blob/main/docs/policy.md)
- [Presets](https://github.com/pinestraw/testradar/blob/main/docs/presets.md)
- [Design](https://github.com/pinestraw/testradar/blob/main/docs/design.md)
- [Benchmarks](https://github.com/pinestraw/testradar/blob/main/docs/benchmarks.md)
- [Static-only analysis rationale](https://github.com/pinestraw/testradar/blob/main/docs/static_only_analysis.md)

## Status

This repository currently implements:

- the static analysis engine
- incremental graph storage
- the CLI
- the pytest deselection plugin
- the Django preset
- synthetic tests and downstream validation

Dynamic coverage-context refinement is intentionally deferred until the
static-only savings are proven across downstream consumers.
