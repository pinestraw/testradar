# Integration Guide

## Install

```bash
pip install testradar
```

For Django-specific policy and detectors:

```bash
pip install 'testradar[django]'
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

## Build the graph

```bash
testradar index
```

## Emit targets

```bash
testradar select > .testradar/targets.txt
pytest -p testradar.pytest_plugin --testradar .testradar/targets.txt
```

## Inspect classification

```bash
testradar classify --json
```

## Audit miss rate

```bash
testradar audit --selected selected.json --failed failed.txt
```
