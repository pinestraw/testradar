from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import testradar

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_uses_single_source_hatch_versioning() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["dynamic"] == ["version"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "src/testradar/__init__.py"


def test_release_version_script_reads_runtime_version() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "read_version.py")],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == testradar.__version__


def test_release_version_script_rejects_mismatched_tag() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "read_version.py"), "--check-tag", "v999.0.0"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "does not match package version" in result.stderr


def test_project_urls_and_classifiers_are_present() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["urls"]["Homepage"] == "https://github.com/pinestraw/testradar"
    assert project["urls"]["Documentation"] == "https://github.com/pinestraw/testradar#readme"
    assert project["urls"]["Repository"] == "https://github.com/pinestraw/testradar"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert "Programming Language :: Python :: 3.9" in project["classifiers"]
    assert "Programming Language :: Python :: 3.13" in project["classifiers"]
    assert "Typing :: Typed" in project["classifiers"]


def test_release_workflow_uses_trusted_publishing() -> None:
    workflow_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    required_markers = [
        "workflow_dispatch:",
        "publish_testpypi:",
        "tags:",
        '- "v*"',
        "environment:",
        "name: testpypi",
        "name: pypi",
        "id-token: write",
        "pypa/gh-action-pypi-publish@",
        "repository-url: https://test.pypi.org/legacy/",
        "python scripts/read_version.py --check-tag",
        "python -m build --no-isolation",
        "python -m pip install build twine hatchling",
        "twine check --strict dist/*",
        "python scripts/check_dist.py dist/*",
        'if: startsWith(github.ref, \'refs/tags/v\')',
        'group: release-${{ github.ref }}',
        "softprops/action-gh-release@",
        "contents: write",
    ]

    missing = [marker for marker in required_markers if marker not in workflow_text]
    assert not missing, f"Missing release workflow markers: {missing}"

    pinned_actions = [
        r"actions/checkout@[0-9a-f]{40}",
        r"actions/setup-python@[0-9a-f]{40}",
        r"actions/upload-artifact@[0-9a-f]{40}",
        r"actions/download-artifact@[0-9a-f]{40}",
        r"pypa/gh-action-pypi-publish@[0-9a-f]{40}",
        r"softprops/action-gh-release@[0-9a-f]{40}",
    ]
    for pattern in pinned_actions:
        assert re.search(pattern, workflow_text), f"Missing pinned action matching {pattern}"


def test_ci_workflow_validates_build_artifacts() -> None:
    workflow_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    required_markers = [
        'python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]',
        "python -m build --no-isolation",
        "twine check --strict dist/*",
        "python scripts/check_dist.py dist/*",
        "python -m pip install build twine hatchling",
        'python -m pip install "$(ls dist/*.whl)"',
        "testradar --help",
        "actions/checkout@",
        "actions/setup-python@",
    ]

    missing = [marker for marker in required_markers if marker not in workflow_text]
    assert not missing, f"Missing CI workflow markers: {missing}"


def test_makefile_exposes_release_automation_targets() -> None:
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")

    required_markers = [
        "bootstrap-dev:",
        "test:",
        "package:",
        "smoke-wheel:",
        "release-check:",
        "print-version:",
        "./scripts/find_python.sh",
        "./scripts/pip_user_install.sh",
        "-m build --no-isolation",
        "scripts/check_dist.py",
        "pip install --target",
    ]

    missing = [marker for marker in required_markers if marker not in makefile_text]
    assert not missing, f"Missing Makefile markers: {missing}"
