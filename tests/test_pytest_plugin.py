from __future__ import annotations

from testradar.pytest_plugin import _matches_target, pytest_addoption, pytest_collection_modifyitems


class FakeParser:
    def __init__(self):
        self.calls = []

    def addoption(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class FakeHook:
    def __init__(self):
        self.deselected = None

    def pytest_deselected(self, *, items):
        self.deselected = items


class FakeConfig:
    def __init__(self, selected_path):
        self._selected_path = selected_path
        self.hook = FakeHook()

    def getoption(self, name):
        assert name == "--testradar"
        return self._selected_path


class FakeItem:
    def __init__(self, nodeid):
        self.nodeid = nodeid


def test_pytest_addoption_registers_flag():
    parser = FakeParser()

    pytest_addoption(parser)

    assert parser.calls[0][0] == ("--testradar",)
    assert parser.calls[0][1]["action"] == "store"


def test_collection_modifyitems_returns_early_without_target_file(tmp_path):
    items = [FakeItem("tests/test_one.py::test_it")]
    config = FakeConfig(None)

    pytest_collection_modifyitems(config, items)

    assert [item.nodeid for item in items] == ["tests/test_one.py::test_it"]
    assert config.hook.deselected is None

    empty_path = tmp_path / "targets.txt"
    empty_path.write_text("", encoding="utf-8")
    config = FakeConfig(str(empty_path))
    pytest_collection_modifyitems(config, items)
    assert [item.nodeid for item in items] == ["tests/test_one.py::test_it"]


def test_collection_modifyitems_filters_and_matches_parametrized_targets(tmp_path):
    target_path = tmp_path / "targets.txt"
    target_path.write_text("tests/test_mod.py::test_two\n", encoding="utf-8")
    items = [
        FakeItem("tests/test_mod.py::test_one"),
        FakeItem("tests/test_mod.py::test_two[param]"),
        FakeItem("tests/test_other.py::test_three"),
    ]
    config = FakeConfig(str(target_path))

    pytest_collection_modifyitems(config, items)

    assert [item.nodeid for item in items] == ["tests/test_mod.py::test_two[param]"]
    assert [item.nodeid for item in config.hook.deselected] == [
        "tests/test_mod.py::test_one",
        "tests/test_other.py::test_three",
    ]
    assert _matches_target("tests/test_mod.py::test_two[param]", "tests/test_mod.py::test_two") is True
    assert _matches_target("tests/test_mod.py::test_one", "tests/test_mod.py") is True
    assert _matches_target("tests/test_other.py::test_three", "tests/test_mod.py") is False
