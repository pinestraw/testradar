# Static-Only Analysis

The current package intentionally ships static-only selection.

## Why

- The static graph is simpler to validate and easier to reason about.
- It preserves the core safety rule: widen on uncertainty.
- The mandate's own Phase 0 asks for proof that static-only savings are insufficient before adding a dynamic layer.

## Current package stance

- `testradar.select` is the static floor.
- `testradar.cov.ingest` and `testradar.cov.query` are explicit placeholders rather than half-integrated behavior.
- Any future dynamic layer must prove `select() ⊇ static_only_select()` and never narrow below the static result.

## Next consumer-side step

Run the static engine against recent real PRs in the downstream repo and compare:

- full suite size
- static-only selected subset size
- observed misses in a shadow run

Until that evidence exists, keeping the package static-only is the correct default.
