# Policy

The default policy is intentionally small and framework-agnostic.

## Default rules

- `conftest.py` at repo root selects the full suite.
- Nested `conftest.py` selects tests in that subtree.
- Lockfiles and packaging/config files such as `pyproject.toml`, `setup.py`, and `setup.cfg` select the full suite.
- Python test files are identified by filename patterns such as `test_*.py` and `*_test.py`.
- Support modules such as `conftest.py`, `__init__.py`, and `tests/helpers.py` are not treated as runnable test targets.
- When a support module feeds a `conftest.py`, `testradar` widens selection to the `conftest` subtree because pytest applies that coupling implicitly.
- `pytest_plugins = [...]` string registrations are treated as dependency edges.

## Over-selection rules

When `testradar` cannot safely narrow selection, it widens:

- Decorated or parametrized tests fall back to the whole file.
- Source parse failures select all discovered tests.
- Renames use the previous graph for the deleted side and the current graph for the added side.
- Dynamic import strings are treated as graph edges when they can be statically extracted.

This package currently prefers predictable safety over maximum narrowing.
