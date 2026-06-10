from __future__ import annotations

import ast
from pathlib import Path

from testradar.detectors.django import (
    DjangoCouplingDetector,
    _call_name as django_call_name,
    _const_str,
    _detect_connect_sender,
    _detect_get_model,
    _detect_receiver_sender,
    _sender_label_to_module,
)
from testradar.detectors.generic import GenericDynamicImportDetector, _call_name as generic_call_name
from testradar.detectors.pytest import PytestPluginDetector, _extract_plugin_requests


def test_generic_dynamic_import_detector_and_helper_branches():
    tree = ast.parse(
        """
import importlib

ONE = importlib.import_module("pkg.alpha")
TWO = import_module("pkg.beta")
THREE = __import__("pkg.gamma")
FOUR = importlib.import_module()
FIVE = importlib.import_module(NAME)
""",
    )

    detector = GenericDynamicImportDetector()
    results = detector.detect(tree=tree, path=Path("x.py"), module="pkg.loader")

    assert [item.module for item in results] == ["pkg.alpha", "pkg.beta", "pkg.gamma"]
    assert generic_call_name(ast.parse("value").body[0].value) == "value"
    assert generic_call_name(ast.parse("pkg.value").body[0].value) == "pkg.value"
    assert generic_call_name(ast.parse("call().value").body[0].value) is None


def test_pytest_plugin_detector_handles_assign_and_annassign():
    tree = ast.parse(
        """
pytest_plugins = ["pkg.alpha", "pkg.beta", 3]
pytest_plugins: list[str] = "pkg.gamma"
other = ["ignored"]
""",
    )

    detector = PytestPluginDetector()
    results = detector.detect(tree=tree, path=Path("conftest.py"), module="tests.conftest")

    assert [item.module for item in results] == ["pkg.alpha", "pkg.beta", "pkg.gamma"]
    assert _extract_plugin_requests(ast.parse("VALUE").body[0].value) == []


def test_django_detector_helpers_cover_non_match_and_match_paths():
    get_model = ast.parse('apps.get_model("billing", "Invoice")').body[0].value
    assert [item.module for item in _detect_get_model(get_model)] == ["billing.models"]

    too_few_args = ast.parse('apps.get_model("billing")').body[0].value
    assert _detect_get_model(too_few_args) == []

    non_string_arg = ast.parse("apps.get_model(NAME, 'Invoice')").body[0].value
    assert _detect_get_model(non_string_arg) == []

    connect_sender = ast.parse('signal.connect(sender="billing.Invoice")').body[0].value
    assert [item.module for item in _detect_connect_sender(connect_sender)] == ["billing.models"]

    wrong_call = ast.parse("signal.send(sender='billing.Invoice')").body[0].value
    assert _detect_connect_sender(wrong_call) == []

    no_sender = ast.parse("signal.connect(value='billing.Invoice')").body[0].value
    assert _detect_connect_sender(no_sender) == []

    bad_sender = ast.parse("signal.connect(sender=NAME)").body[0].value
    assert _detect_connect_sender(bad_sender) == []

    no_dot_sender = ast.parse('signal.connect(sender="Invoice")').body[0].value
    assert _detect_connect_sender(no_dot_sender) == []

    receiver_fn = ast.parse(
        """
@receiver(post_save, sender="billing.Invoice")
def handle(sender, **kwargs):
    return None
""",
    ).body[0]
    assert [item.module for item in _detect_receiver_sender(receiver_fn)] == ["billing.models"]

    async_receiver = ast.parse(
        """
@receiver(post_save, sender=NAME)
async def handle(sender, **kwargs):
    return None
""",
    ).body[0]
    assert _detect_receiver_sender(async_receiver) == []

    assert _sender_label_to_module("billing.Invoice") == "billing.models"
    assert _sender_label_to_module("Invoice") is None
    assert _const_str(ast.parse("'value'").body[0].value) == "value"
    assert _const_str(ast.parse("NAME").body[0].value) is None
    assert django_call_name(ast.parse("name").body[0].value) == "name"
    assert django_call_name(ast.parse("pkg.name").body[0].value) == "pkg.name"
    assert django_call_name(ast.parse("call().name").body[0].value) is None


def test_django_detector_detect_collects_call_and_function_cases():
    tree = ast.parse(
        """
from django.dispatch import receiver

MODEL = apps.get_model("billing", "Invoice")
signal.connect(sender="billing.Invoice")

@receiver(post_save, sender="billing.Invoice")
def handle(sender, **kwargs):
    return None
""",
    )

    detector = DjangoCouplingDetector()
    results = detector.detect(tree=tree, path=Path("signals.py"), module="billing.signals")

    assert [item.module for item in results] == [
        "billing.models",
        "billing.models",
        "billing.models",
    ]
