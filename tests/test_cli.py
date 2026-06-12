from __future__ import annotations

import json
from importlib import import_module, reload
from pathlib import Path

import pytest

import testradar
from testradar import cli


def test_package_metadata_and_main_module(monkeypatch):
    monkeypatch.setattr("testradar.cli.main", lambda argv=None: 7)
    main_module = import_module("testradar.__main__")

    with pytest.raises(SystemExit) as exc_info:
        main_module.run()

    assert exc_info.value.code == 7
    assert testradar.__version__ == "0.2.2"
    assert testradar.__all__ == ["__version__"]


def test_runtime_imports_cover_entry_modules(monkeypatch):
    monkeypatch.setattr("testradar.cli.main", lambda argv=None: 3)

    package = reload(import_module("testradar"))
    plugin = reload(import_module("testradar.pytest_plugin"))
    main_module = import_module("testradar.__main__")

    assert package.__version__ == "0.2.2"
    assert callable(plugin.pytest_addoption)

    main_path = Path(main_module.__file__)
    with pytest.raises(SystemExit) as exc_info:
        exec(compile(main_path.read_text(encoding="utf-8"), str(main_path), "exec"), {"__name__": "__main__"})

    assert exc_info.value.code == 3


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
    targets_path = repo.root / "reports" / "selection.txt"
    assert cli.main(
        [
            "--repo-root",
            str(repo.root),
            "select",
            "--report",
            str(report_path),
            "--targets-file",
            str(targets_path),
        ],
    ) == 0
    text_output = capsys.readouterr().out
    assert "tests/test_service.py" in text_output
    assert report_path.exists()
    assert targets_path.read_text(encoding="utf-8") == "tests/test_service.py\n"
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_payload["targets"][0]["target"] == "tests/test_service.py"
    assert report_payload["target_count"] == 1
    assert report_payload["comparison_mode"] == "merge-base-to-working-tree"
    assert report_payload["resolved_base"]
    assert report_payload["resolved_head"]

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


def test_main_passes_git_overrides_to_load_config(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_load_config(repo_root, **kwargs):
        captured["repo_root"] = repo_root
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("testradar.cli.load_config", fake_load_config)
    monkeypatch.setattr("testradar.cli._handle_index", lambda _args, _config: 0)

    assert cli.main(
        [
            "--repo-root",
            str(tmp_path),
            "--diff-base",
            "origin/main",
            "--diff-head",
            "HEAD",
            "--git-dir",
            "/git-common/worktrees/feature",
            "--git-work-tree",
            "/code",
            "--on-unclassified",
            "full-suite",
            "index",
        ],
    ) == 0

    assert captured["repo_root"] == tmp_path.resolve()
    assert captured["diff_base"] == "origin/main"
    assert captured["diff_head"] == "HEAD"
    assert captured["git_dir"] == "/git-common/worktrees/feature"
    assert captured["git_work_tree"] == "/code"
    assert captured["on_unclassified"] == "full-suite"


def test_main_select_fails_closed_for_unclassified_changes(repo, capsys):
    repo.write("tests/test_one.py", "def test_one():\n    assert True\n")
    repo.commit_all()
    repo.write(".github/workflows/deploy.yml", "name: deploy\n")

    assert cli.main(
        [
            "--repo-root",
            str(repo.root),
            "--on-unclassified",
            "fail",
            "select",
        ],
    ) == 1

    captured = capsys.readouterr()
    assert "Unclassified changed files require a policy decision" in captured.err
    assert ".github/workflows/deploy.yml" in captured.err


def test_main_requires_explicit_diff_pair(repo):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--repo-root", str(repo.root), "--diff-base", "origin/main", "select"])

    assert exc_info.value.code == 2
