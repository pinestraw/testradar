# ruff: noqa: E402

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from testradar.config import load_config
from testradar.graph.store import load_graph
from testradar.select import index_repository, select_targets


@dataclass
class RepoHarness:
    root: Path

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            text=True,
            capture_output=True,
        )

    def commit_all(self, message: str = "base") -> None:
        self.git("add", ".")
        self.git("commit", "-m", message)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def config(self, **kwargs):
        return load_config(self.root, base_ref="HEAD", **kwargs)

    def index(self):
        return index_repository(self.config())

    def select(self, **kwargs):
        return select_targets(self.config(**kwargs))

    def graph(self):
        return load_graph(self.config().graph_path)


@pytest.fixture
def repo(tmp_path: Path) -> RepoHarness:
    harness = RepoHarness(tmp_path)
    harness.git("init")
    harness.git("branch", "-M", "main")
    harness.git("config", "user.email", "testradar@example.com")
    harness.git("config", "user.name", "testradar")
    harness.write(
        "pyproject.toml",
        """
        [build-system]
        requires = ["hatchling>=1.26"]
        build-backend = "hatchling.build"

        [tool.testradar]
        base_ref = "HEAD"
        source_roots = ["."]
        graph_path = ".testradar/graph.msgpack"
        """,
    )
    return harness


def configure_django(repo: RepoHarness) -> None:
    repo.write(
        "pyproject.toml",
        """
        [build-system]
        requires = ["hatchling>=1.26"]
        build-backend = "hatchling.build"

        [tool.testradar]
        base_ref = "HEAD"
        source_roots = ["."]
        graph_path = ".testradar/graph.msgpack"
        preset = "django"
        """,
    )
