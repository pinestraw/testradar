# Benchmarks

This repository now contains the static engine and incremental graph update path needed for downstream benchmarking.

## Status

Consumer-repo benchmarks against `jungle` are not recorded in this repo yet. The mandate issue calls for:

- cold full parse on the real `jungle` tree
- warm incremental select on a 1-20 file diff
- confirmation that the path does not import pytest, Django, or the database

## Recommended benchmark flow

Run these commands from a `jungle` checkout after installing `testradar`:

```bash
testradar --repo-root /path/to/jungle --base-ref origin/staging --graph-path /tmp/jungle-graph.msgpack index
testradar --repo-root /path/to/jungle --base-ref origin/staging --graph-path /tmp/jungle-graph.msgpack select
```

Measure:

- cold `index`
- warm `select` after a 1-file source edit
- warm `select` after a 10-20 file mixed edit

The package is ready for those measurements; this repo does not yet bundle a dedicated benchmark harness.
