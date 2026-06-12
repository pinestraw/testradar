from __future__ import annotations

from testradar.select import static_only_select

from conftest import configure_django


def test_selects_changed_test_function(repo):
    repo.write(
        "tests/test_math.py",
        """
        def test_add():
            value = 1 + 1
            assert value == 2

        def test_subtract():
            value = 4 - 1
            assert value == 3
        """,
    )
    repo.commit_all()
    repo.write(
        "tests/test_math.py",
        """
        def test_add():
            value = 2 + 2
            assert value == 4

        def test_subtract():
            value = 4 - 1
            assert value == 3
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_math.py::test_add"]
    assert static_only_select(repo.config()).target_strings() == result.target_strings()


def test_parametrized_test_falls_back_to_whole_file(repo):
    repo.write(
        "tests/test_math.py",
        """
        import pytest

        @pytest.mark.parametrize("value", [1, 2])
        def test_add(value):
            assert value + 1 > value
        """,
    )
    repo.commit_all()
    repo.write(
        "tests/test_math.py",
        """
        import pytest

        @pytest.mark.parametrize("value", [1, 2])
        def test_add(value):
            assert value + 2 > value
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_math.py"]


def test_subtree_conftest_selects_local_tests(repo):
    repo.write("tests/subpkg/conftest.py", "VALUE = 1\n")
    repo.write("tests/subpkg/test_local.py", "def test_local():\n    assert True\n")
    repo.write("tests/test_root.py", "def test_root():\n    assert True\n")
    repo.commit_all()
    repo.write("tests/subpkg/conftest.py", "VALUE = 2\n")

    result = repo.select()

    assert result.target_strings() == ["tests/subpkg/test_local.py"]


def test_support_module_inside_tests_is_treated_as_source(repo):
    repo.write("tests/helpers.py", "VALUE = 1\n")
    repo.write(
        "tests/test_consumer.py",
        """
        from tests import helpers

        def test_value():
            assert helpers.VALUE == 1
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write("tests/helpers.py", "VALUE = 2\n")

    result = repo.select()

    assert result.target_strings() == ["tests/test_consumer.py"]


def test_conftest_import_dependency_selects_subtree_tests(repo):
    repo.write("tests/subpkg/support.py", "VALUE = 1\n")
    repo.write(
        "tests/subpkg/conftest.py",
        """
        from tests.subpkg import support

        VALUE = support.VALUE
        """,
    )
    repo.write("tests/subpkg/test_local.py", "def test_local():\n    assert True\n")
    repo.write("tests/test_root.py", "def test_root():\n    assert True\n")
    repo.commit_all()
    repo.index()
    repo.write("tests/subpkg/support.py", "VALUE = 2\n")

    result = repo.select()

    assert result.target_strings() == ["tests/subpkg/test_local.py"]


def test_pytest_plugins_string_dependency_selects_subtree_tests(repo):
    repo.write("tests/subpkg/fixtures.py", "VALUE = 1\n")
    repo.write(
        "tests/subpkg/conftest.py",
        """
        pytest_plugins = ["tests.subpkg.fixtures"]
        """,
    )
    repo.write("tests/subpkg/test_local.py", "def test_local():\n    assert True\n")
    repo.write("tests/test_root.py", "def test_root():\n    assert True\n")
    repo.commit_all()
    repo.index()
    repo.write("tests/subpkg/fixtures.py", "VALUE = 2\n")

    result = repo.select()

    assert result.target_strings() == ["tests/subpkg/test_local.py"]


def test_root_conftest_selects_full_suite(repo):
    repo.write("conftest.py", "VALUE = 1\n")
    repo.write("tests/test_one.py", "def test_one():\n    assert True\n")
    repo.write("tests/test_two.py", "def test_two():\n    assert True\n")
    repo.commit_all()
    repo.write("conftest.py", "VALUE = 2\n")

    result = repo.select()

    assert result.full_suite is True
    assert result.target_strings() == ["tests/test_one.py", "tests/test_two.py"]


def test_unclassified_change_is_ignored_by_default(repo):
    repo.write("tests/test_one.py", "def test_one():\n    assert True\n")
    repo.write("tests/test_two.py", "def test_two():\n    assert True\n")
    repo.commit_all()
    repo.write(".github/workflows/deploy.yml", "name: deploy\n")

    result = repo.select()

    assert result.full_suite is False
    assert result.target_strings() == []
    assert result.escalations == []


def test_unclassified_change_can_escalate_to_full_suite(repo):
    repo.write("tests/test_one.py", "def test_one():\n    assert True\n")
    repo.write("tests/test_two.py", "def test_two():\n    assert True\n")
    repo.commit_all()
    repo.write(".github/workflows/deploy.yml", "name: deploy\n")

    result = repo.select(on_unclassified="full-suite")

    assert result.full_suite is True
    assert result.target_strings() == ["tests/test_one.py", "tests/test_two.py"]
    assert result.escalations == [".github/workflows/deploy.yml: unclassified-change -> full-suite"]
    assert result.reasons == [".github/workflows/deploy.yml: no-policy-match"]


def test_ast_parse_error_falls_back_to_known_dependents(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.write("tests/test_service.py", "from app import service\n\ndef test_value():\n    assert service.VALUE == 1\n")
    repo.write("tests/test_other.py", "def test_other():\n    assert True\n")
    repo.commit_all()
    repo.index()
    repo.write("app/service.py", "def broken(:\n")

    result = repo.select()

    assert result.escalations == ["app/service.py: parse-error fallback (invalid syntax (service.py, line 1))"]
    assert result.target_strings() == ["tests/test_service.py"]


def test_legacy_except_syntax_allows_source_nodeid_narrowing(repo):
    repo.write("app/__init__.py", "")
    repo.write(
        "app/service.py",
        """
        def alpha():
            try:
                return 1
            except TypeError, ValueError:
                return 0

        def beta():
            return 2
        """,
    )
    repo.write(
        "tests/test_service.py",
        """
        from app.service import alpha, beta

        def test_alpha():
            assert alpha() == 1

        def test_beta():
            assert beta() == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write(
        "app/service.py",
        """
        def alpha():
            try:
                return 3
            except TypeError, ValueError:
                return 0

        def beta():
            return 2
        """,
    )

    result = repo.select()

    assert result.escalations == []
    assert result.target_strings() == ["tests/test_service.py::test_alpha"]


def test_lazy_conftest_dependency_does_not_expand_to_full_suite(repo):
    repo.write("app/__init__.py", "")
    repo.write("app/service.py", "VALUE = 1\n")
    repo.write(
        "bridge.py",
        """
        from importlib import import_module

        def load_service_value():
            module = import_module("app.service")
            return module.VALUE

        def load_service_again():
            from app import service

            return service.VALUE
        """,
    )
    repo.write(
        "conftest.py",
        """
        import pytest
        import bridge

        @pytest.fixture(autouse=True)
        def noop_fixture():
            assert bridge is not None
        """,
    )
    repo.write("tests/test_service.py", "from app import service\n\ndef test_value():\n    assert service.VALUE == 1\n")
    repo.write("tests/test_other.py", "def test_other():\n    assert True\n")
    repo.commit_all()
    repo.index()
    repo.write("app/service.py", "VALUE = 2\n")

    result = repo.select()

    assert result.target_strings() == ["tests/test_service.py"]


def test_rename_uses_previous_graph_for_dependents(repo):
    repo.write("pkg/__init__.py", "")
    repo.write("pkg/old.py", "VALUE = 1\n")
    repo.write("pkg/service.py", "from pkg import old\n\nVALUE = old.VALUE\n")
    repo.write("tests/test_service.py", "from pkg import service\n\ndef test_value():\n    assert service.VALUE == 1\n")
    repo.commit_all()
    repo.index()
    repo.git("mv", "pkg/old.py", "pkg/new.py")

    result = repo.select()

    assert result.target_strings() == ["tests/test_service.py"]


def test_reexported_package_symbols_do_not_select_unrelated_importers(repo):
    repo.write(
        "pkg/__init__.py",
        """
        from .alpha import Alpha
        from .beta import Beta
        """,
    )
    repo.write("pkg/alpha.py", "class Alpha:\n    VALUE = 1\n")
    repo.write("pkg/beta.py", "class Beta:\n    VALUE = 2\n")
    repo.write(
        "pkg/use_alpha.py",
        """
        from pkg import Alpha

        VALUE = Alpha.VALUE
        """,
    )
    repo.write(
        "pkg/use_beta.py",
        """
        from pkg import Beta

        VALUE = Beta.VALUE
        """,
    )
    repo.write(
        "tests/test_alpha.py",
        """
        from pkg import use_alpha

        def test_alpha():
            assert use_alpha.VALUE == 1
        """,
    )
    repo.write(
        "tests/test_beta.py",
        """
        from pkg import use_beta

        def test_beta():
            assert use_beta.VALUE == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write("pkg/alpha.py", "class Alpha:\n    VALUE = 3\n")

    result = repo.select()

    assert result.target_strings() == ["tests/test_alpha.py"]


def test_source_change_selects_directly_impacted_test_function(repo):
    repo.write("app/__init__.py", "")
    repo.write(
        "app/service.py",
        """
        def foo():
            return 1

        def bar():
            return 2
        """,
    )
    repo.write(
        "tests/test_service.py",
        """
        from app import service

        def test_foo():
            assert service.foo() == 1

        def test_bar():
            assert service.bar() == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write(
        "app/service.py",
        """
        def foo():
            return 10

        def bar():
            return 2
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_service.py::test_foo"]


def test_source_change_tracks_module_helper_usage(repo):
    repo.write("app/__init__.py", "")
    repo.write(
        "app/service.py",
        """
        def foo():
            return 1

        def bar():
            return 2
        """,
    )
    repo.write(
        "tests/test_service.py",
        """
        from app import service

        def call_foo():
            return service.foo()

        def call_bar():
            return service.bar()

        def test_foo():
            assert call_foo() == 1

        def test_bar():
            assert call_bar() == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write(
        "app/service.py",
        """
        def foo():
            return 10

        def bar():
            return 2
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_service.py::test_foo"]


def test_indirect_source_dependency_keeps_whole_test_file(repo):
    repo.write("app/__init__.py", "")
    repo.write(
        "app/service.py",
        """
        def foo():
            return 1

        def bar():
            return 2
        """,
    )
    repo.write(
        "app/api.py",
        """
        from app import service

        def run_foo():
            return service.foo()

        def run_bar():
            return service.bar()
        """,
    )
    repo.write(
        "tests/test_api.py",
        """
        from app import api

        def test_foo():
            assert api.run_foo() == 1

        def test_bar():
            assert api.run_bar() == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write(
        "app/service.py",
        """
        def foo():
            return 10

        def bar():
            return 2
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_api.py"]


def test_module_level_execution_keeps_whole_test_file(repo):
    repo.write("app/__init__.py", "")
    repo.write(
        "app/service.py",
        """
        def foo():
            return 1

        def bar():
            return 2
        """,
    )
    repo.write(
        "tests/test_service.py",
        """
        from app import service

        VALUE = service.foo()

        def test_foo():
            assert VALUE == 1

        def test_bar():
            assert VALUE == 1
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write(
        "app/service.py",
        """
        def foo():
            return 10

        def bar():
            return 2
        """,
    )

    result = repo.select()

    assert result.target_strings() == ["tests/test_service.py"]


def test_dynamic_imported_package_symbols_do_not_select_unrelated_importers(repo):
    repo.write(
        "pkg/__init__.py",
        """
        from .alpha import Alpha
        from .beta import Beta
        """,
    )
    repo.write("pkg/alpha.py", "class Alpha:\n    VALUE = 1\n")
    repo.write("pkg/beta.py", "class Beta:\n    VALUE = 2\n")
    repo.write(
        "pkg/use_alpha.py",
        """
        from importlib import import_module

        package = import_module("pkg")
        VALUE = package.Alpha.VALUE
        """,
    )
    repo.write(
        "pkg/use_beta.py",
        """
        from importlib import import_module

        VALUE = import_module("pkg").Beta.VALUE
        """,
    )
    repo.write(
        "tests/test_alpha.py",
        """
        from pkg import use_alpha

        def test_alpha():
            assert use_alpha.VALUE == 1
        """,
    )
    repo.write(
        "tests/test_beta.py",
        """
        from pkg import use_beta

        def test_beta():
            assert use_beta.VALUE == 2
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write("pkg/alpha.py", "class Alpha:\n    VALUE = 3\n")

    result = repo.select()

    assert result.target_strings() == ["tests/test_alpha.py"]


def test_django_settings_change_selects_full_suite(repo):
    configure_django(repo)
    repo.write("project/settings.py", "DEBUG = False\n")
    repo.write("tests/test_one.py", "def test_one():\n    assert True\n")
    repo.write("tests/test_two.py", "def test_two():\n    assert True\n")
    repo.commit_all()
    repo.write("project/settings.py", "DEBUG = True\n")

    result = repo.select()

    assert result.full_suite is True
    assert result.target_strings() == ["tests/test_one.py", "tests/test_two.py"]


def test_django_migration_selects_app_scope(repo):
    configure_django(repo)
    repo.write("billing/__init__.py", "")
    repo.write("billing/migrations/0001_initial.py", "MIGRATION = 1\n")
    repo.write("billing/tests/test_models.py", "def test_models():\n    assert True\n")
    repo.write("tests/billing/test_api.py", "def test_api():\n    assert True\n")
    repo.write("tests/test_other.py", "def test_other():\n    assert True\n")
    repo.commit_all()
    repo.write("billing/migrations/0001_initial.py", "MIGRATION = 2\n")

    result = repo.select()

    assert result.target_strings() == ["billing/tests/test_models.py", "tests/billing/test_api.py"]


def test_django_get_model_detector_selects_dependents(repo):
    configure_django(repo)
    repo.write("billing/__init__.py", "")
    repo.write("billing/models.py", "class Invoice:\n    pass\n")
    repo.write(
        "billing/signals.py",
        """
        from django.apps import apps

        MODEL = apps.get_model("billing", "Invoice")
        """,
    )
    repo.write(
        "tests/test_signals.py",
        """
        from billing import signals

        def test_model():
            assert signals.MODEL
        """,
    )
    repo.commit_all()
    repo.index()
    repo.write("billing/models.py", "class Invoice:\n    status = 'paid'\n")

    result = repo.select()

    assert result.target_strings() == ["tests/test_signals.py"]
