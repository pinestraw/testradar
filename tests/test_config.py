from __future__ import annotations

from pathlib import Path

import pytest

from testradar.config import _ensure_tuple, load_config


def test_load_config_uses_defaults_without_pyproject(tmp_path: Path):
    config = load_config(tmp_path)

    assert config.base_ref == "origin/main"
    assert config.source_roots == (tmp_path.resolve(),)
    assert config.graph_path == (tmp_path / ".testradar/graph.msgpack").resolve()
    assert config.git_dir is None
    assert config.git_work_tree is None
    assert config.test_file_patterns == ("test_*.py", "*_test.py")
    assert ".coverage*" in config.ignored_path_patterns


def test_load_config_reads_strings_lists_and_absolute_graph_path(tmp_path: Path):
    graph_path = tmp_path / "custom.msgpack"
    (tmp_path / "pyproject.toml").write_text(
        f"""
[tool.testradar]
base_ref = "origin/staging"
source_roots = ["src", "tests"]
graph_path = "{graph_path}"
git_dir = ".git/worktrees/feature"
git_work_tree = "."
preset = "django"
presets = ["custom"]
detectors = ["pkg.module:Detector"]
test_file_patterns = ["spec_*.py"]
lockfile_patterns = ["deps.lock"]
global_patterns = ["project.toml"]
ignored_path_patterns = ["coverage", "reports/*"]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.base_ref == "origin/staging"
    assert config.source_roots == ((tmp_path / "src").resolve(), (tmp_path / "tests").resolve())
    assert config.graph_path == graph_path
    assert config.git_dir == (tmp_path / ".git/worktrees/feature").resolve()
    assert config.git_work_tree == tmp_path.resolve()
    assert config.presets == ("custom", "django")
    assert config.detector_paths == ("pkg.module:Detector",)
    assert config.test_file_patterns == ("spec_*.py",)
    assert config.lockfile_patterns == ("deps.lock",)
    assert config.global_patterns == ("project.toml",)
    assert config.ignored_path_patterns == ("coverage", "reports/*")


def test_load_config_prefers_explicit_git_overrides(tmp_path: Path):
    config = load_config(
        tmp_path,
        git_dir="/git-common/worktrees/feature",
        git_work_tree="/code",
    )

    assert config.git_dir == Path("/git-common/worktrees/feature")
    assert config.git_work_tree == Path("/code")


def test_load_config_rejects_invalid_tool_table(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool]
testradar = "bad"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a table"):
        load_config(tmp_path)


def test_ensure_tuple_rejects_invalid_values():
    with pytest.raises(ValueError, match="field must be a string or list of strings"):
        _ensure_tuple(3, field_name="field")

    with pytest.raises(ValueError, match="field must be a string or list of strings"):
        _ensure_tuple(["ok", 3], field_name="field")
