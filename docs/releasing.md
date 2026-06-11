# Releasing

This repository is wired for GitHub Actions + Trusted Publishing.

The intended release flow is:

1. update the package version in `src/testradar/__init__.py`
2. merge to `main`
3. push a version tag like `v0.2.0`
4. let GitHub Actions build the distributions
5. publish to TestPyPI
6. publish to PyPI after TestPyPI succeeds
7. create a GitHub release with the built artifacts attached

The workflows for this live in:

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

## One-time setup

### 1. Create GitHub environments

Create these environments in the GitHub repository settings:

- `testpypi`
- `pypi`

Recommended protection:

- `testpypi`: no manual approval
- `pypi`: require manual approval from maintainers

### 2. Register Trusted Publishers on TestPyPI

Go to:

- `https://test.pypi.org/manage/account/publishing/`

Create a pending publisher with:

- PyPI project name: `testradar`
- GitHub owner: `pinestraw`
- GitHub repository name: `testradar`
- workflow filename: `release.yml`
- environment name: `testpypi`

### 3. Register Trusted Publishers on PyPI

Go to:

- `https://pypi.org/manage/account/publishing/`

Create a pending publisher with:

- PyPI project name: `testradar`
- GitHub owner: `pinestraw`
- GitHub repository name: `testradar`
- workflow filename: `release.yml`
- environment name: `pypi`

If the project does not exist on PyPI yet, this pending publisher is enough for
the first release. PyPI will create the project on first successful publish.
Until that first publish happens, the name is not reserved.

## Versioning

`testradar` now uses a single version source:

- runtime version: `src/testradar/__init__.py`
- build metadata: read by Hatch via `[tool.hatch.version]`
- tag validation: `scripts/read_version.py`

The release workflow verifies that the Git tag matches `src/testradar/__init__.py`.

Example:

- `src/testradar/__init__.py`: `__version__ = "0.2.0"`
- tag: `v0.2.0`

If they do not match, the release workflow fails before uploading anything.

## Release steps

1. update `src/testradar/__init__.py`
2. run the local release check
3. commit to `main`
4. create and push a tag

Example:

```bash
git checkout main
git pull --ff-only
# edit src/testradar/__init__.py
make release-check
git add src/testradar/__init__.py
git commit -m "Release 0.2.0"
git tag v0.2.0
git push origin main --follow-tags
```

The release workflow will then:

- build the wheel and sdist
- build with `python -m build --no-isolation`
- run `twine check --strict`
- validate wheel and sdist contents with `scripts/check_dist.py`
- publish to TestPyPI
- publish to PyPI
- create a GitHub release and attach `dist/*`
- upload PyPI attestations automatically through `pypa/gh-action-pypi-publish`

## Local automation

For maintainers, the repository now ships local release helpers:

```bash
make bootstrap-dev
make release-check
make print-version
```

Notes:

- `make bootstrap-dev` installs into the user site-packages, not a virtualenv
- the helper retries with `--break-system-packages --user` on PEP 668 hosts
- `make release-check` runs pytest, builds `dist/*` with `--no-isolation`,
  validates metadata and dist contents, installs the wheel into a temporary
  target directory, and smoke-runs `python -m testradar --help`

## Supply-chain notes

- GitHub Actions are pinned to immutable commit SHAs
- `release.yml` is isolated to publishing only, which matches PyPI's Trusted
  Publisher security guidance
- `pypa/gh-action-pypi-publish` now emits PyPI attestations automatically when
  using Trusted Publishing
- `.github/dependabot.yml` keeps GitHub Actions and pip dependencies moving

## Dry runs and preview publishes

The `Publish` workflow also supports manual dispatch.

By default it only performs the build and validation steps.

If you set `publish_testpypi=true`, it will additionally publish the selected
ref to TestPyPI.

This is useful when:

- you want to validate the Trusted Publishing plumbing
- you want to test a release candidate before a final PyPI release

Be aware that package indexes do not allow overwriting an existing version. If a
version already exists on TestPyPI, use a new pre-release version such as
`0.2.0rc1` or `0.2.0.dev1`.
