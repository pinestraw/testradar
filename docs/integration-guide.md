# Integration Guide

## Install

Until the package is published to PyPI, install from a checkout or from GitHub.
The local helper targets install into the user site-packages and do not require
a virtualenv.

For local development from a checkout:

```bash
make bootstrap-dev
```

For a direct GitHub install:

```bash
pip install "git+https://github.com/pinestraw/testradar.git"
```

If your user-site bin directory is not on `PATH`, run the CLI as
`python -m testradar`.

Once the package is published, the install becomes:

```bash
pip install testradar
```

## Configure

```toml
[tool.testradar]
base_ref = "origin/main"
source_roots = ["."]
graph_path = ".testradar/graph.msgpack"
```

Optional Django preset:

```toml
[tool.testradar]
preset = "django"
```

Optional fail-closed policy for promotion or deploy jobs:

```toml
[tool.testradar]
on_unclassified = "full-suite"
```

## Build the graph

```bash
testradar index
```

## Emit targets

```bash
testradar select > .testradar/targets.txt
pytest -p testradar.pytest_plugin --testradar .testradar/targets.txt
```

If your CI already knows the exact commit pair being promoted, prefer the
explicit diff mode:

```bash
testradar \
  --diff-base "$DIFF_BASE_SHA" \
  --diff-head "$DIFF_HEAD_SHA" \
  --on-unclassified full-suite \
  select > .testradar/targets.txt
```

This resolves the comparison as `merge-base(diff_base, diff_head)..diff_head`
and keeps repo-specific branch logic outside `testradar`.

## Inspect classification

```bash
testradar classify --json
```

## Audit miss rate

```bash
testradar audit --selected selected.json --failed failed.txt
```
