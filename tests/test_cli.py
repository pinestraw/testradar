from __future__ import annotations

import json
import runpy

import pytest

import testradar
from testradar import cli


def test_package_metadata_and_main_module(monkeypatch):
    monkeypatch.setattr("testradar.cli.main", lambda argv=None: 7)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("testradar.__main__", run_name="__main__")

    assert exc_info.value.code == 7
    assert testradar.__version__ == "0.1.0"
    assert testradar.__all__ == ["__version__"]


def test_main_requires_subcommand(repo):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--repo-root", str(repo.root)])

    assert exc_info.value.code == 2


def test_main_runs_index_and_refresh(repo, capsys):
    assert cli.main(["--repo-root", str(repo.root), "index"]) == 0
    first = json.loads(capsys.readouterr().out)

    assert cli.main(["--repo-root", str(repo.root), "refresh"]) == 0
    second = json.loads(capsys.readouterr().out)

    assert first["graph_mode"] == "full"
    assert second["graph_mode"] == "unchanged"


def test_main_runs_classify_text_and_json(repo, capsys):
    repo.write("tests/test_cli_sample.py", "def test_one():\n    assert True\n")
    repo.commit_all()
    repo.write("tests/test_cli_sample.py", "def test_one():\n    assert False\n")

    assert cli.main(["--repo-root", str(repo.root), "classify"]) == 0
    text_output = capsys.readouterr().out
    assert "tests/test_cli_sample.py\ttest\ttest-file" in text_output

    assert cli.main(["--repo-root", str(repo.root), "classify", "--json"]) == 0
    json_output = json.loads(capsys.readouterr().out)
    assert json_output[0]["scope"] == "test"
    assert json_output[0]["path"] == "tests/test_cli_sample.py"


def test_main_runs_select_with_report_and_json(repo, capsys):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.write(
        "tests/test_service.py",
        """
        from app import service

        def test_value():
            assert service.VALUE == 1
        """,
    )
    repo.commit_all()
    repo.write("app/service.py", "VALUE = 2\n")

    report_path = repo.root / "reports" / "selection.json"
    assert cli.main(
        ["--repo-root", str(repo.root), "select", "--report", str(report_path)],
    ) == 0
    text_output = capsys.readouterr().out
    assert "tests/test_service.py" in text_output
    assert report_path.exists()
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["targets"][0]["target"] == "tests/test_service.py"

    assert cli.main(["--repo-root", str(repo.root), "select", "--json"]) == 0
    json_output = json.loads(capsys.readouterr().out)
    assert json_output["targets"][0]["target"] == "tests/test_service.py"


def test_main_runs_audit(repo, tmp_path, capsys):
    selected = tmp_path / "selected.txt"
    failed = tmp_path / "failed.txt"
    selected.write_text("tests/test_one.py\n", encoding="utf-8")
    failed.write_text("tests/test_one.py\ntests/test_two.py\n", encoding="utf-8")

    assert cli.main(
        [
            "--repo-root",
            str(repo.root),
            "audit",
            "--selected",
            str(selected),
            "--failed",
            str(failed),
        ],
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["missed"] == ["tests/test_two.py"]
    assert payload["miss_rate"] == 0.5


def test_main_uses_graph_path_override(repo, capsys):
    graph_path = repo.root / "state" / "graph.msgpack"

    assert cli.main(
        ["--repo-root", str(repo.root), "--graph-path", str(graph_path), "index"],
    ) == 0
    capsys.readouterr()

    assert graph_path.exists()
