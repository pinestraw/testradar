# Policy

The default policy is intentionally small and framework-agnostic.

Repository-specific operational knowledge should stay outside `testradar`
itself. The core package exposes generic knobs and pattern lists; consuming
repositories decide how strictly to use them.

## Default rules

- `conftest.py` at repo root selects the full suite.
- Nested `conftest.py` selects tests in that subtree.
- Lockfiles and packaging/config files such as `pyproject.toml`, `setup.py`, and `setup.cfg` select the full suite.
- Python test files are identified by filename patterns such as `test_*.py` and `*_test.py`.
- Support modules such as `conftest.py`, `__init__.py`, and `tests/helpers.py` are not treated as runnable test targets.
- When a support module feeds a `conftest.py`, `testradar` widens selection to the `conftest` subtree because pytest applies that coupling implicitly.
- `pytest_plugins = [...]` string registrations are treated as dependency edges.
- Files that match no rule classify as `ignore` with reason `no-policy-match`.

## Over-selection rules

When `testradar` cannot safely narrow selection, it widens:

- Decorated or parametrized tests fall back to the whole file.
- Source parse failures select all discovered tests.
- Renames use the previous graph for the deleted side and the current graph for the added side.
- Dynamic import strings are treated as graph edges when they can be statically extracted.

## Unclassified-file policy

Changed files that classify as `ignore` can be handled three ways through the
generic `on_unclassified` setting or `--on-unclassified` flag:

- `ignore`: preserve the default fail-open behavior
- `full-suite`: escalate to every discovered test file
- `fail`: exit non-zero and surface the offending paths

This is intended for callers that need stricter promotion or deployment gates
without teaching `testradar` about any one repository's directory layout.

This package currently prefers predictable safety over maximum narrowing.
