from __future__ import annotations

import ast
from pathlib import Path

from testradar.models import ImportRequest


class DjangoCouplingDetector:
    name = "django-couplings"

    def detect(
        self,
        *,
        tree: ast.AST,
        path: Path,
        module: str | None,
    ) -> tuple[ImportRequest, ...]:
        results: list[ImportRequest] = []
        parent_map = _build_parent_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                results.extend(_detect_get_model(node, parent_map))
                results.extend(_detect_connect_sender(node, parent_map))
            if isinstance(node, ast.FunctionDef):
                results.extend(_detect_receiver_sender(node))
            if isinstance(node, ast.AsyncFunctionDef):
                results.extend(_detect_receiver_sender(node))
        return tuple(results)


def _detect_get_model(node: ast.Call, parent_map: dict[ast.AST, ast.AST] | None = None) -> list[ImportRequest]:
    dotted = _call_name(node.func)
    if dotted != "apps.get_model":
        return []
    if len(node.args) < 2:
        return []
    app_label = _const_str(node.args[0])
    if app_label is None:
        return []
    return [ImportRequest(module=f"{app_label}.models", is_eager=_is_eager_node(node, parent_map or {}))]


def _detect_connect_sender(node: ast.Call, parent_map: dict[ast.AST, ast.AST] | None = None) -> list[ImportRequest]:
    dotted = _call_name(node.func)
    if not dotted or not dotted.endswith(".connect"):
        return []
    for keyword in node.keywords:
        if keyword.arg != "sender":
            continue
        label = _const_str(keyword.value)
        if label is None:
            return []
        module_name = _sender_label_to_module(label)
        if module_name is None:
            return []
        return [ImportRequest(module=module_name, is_eager=_is_eager_node(node, parent_map or {}))]
    return []


def _detect_receiver_sender(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ImportRequest]:
    results: list[ImportRequest] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        dotted = _call_name(decorator.func)
        if dotted != "receiver":
            continue
        for keyword in decorator.keywords:
            if keyword.arg != "sender":
                continue
            label = _const_str(keyword.value)
            if label is None:
                continue
            module_name = _sender_label_to_module(label)
            if module_name is None:
                continue
            results.append(ImportRequest(module=module_name, is_eager=True))
    return results


def _sender_label_to_module(label: str) -> str | None:
    if "." not in label:
        return None
    app_label, _model_name = label.split(".", 1)
    return f"{app_label}.models"


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parent_map: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent
    return parent_map


def _is_eager_node(node: ast.AST, parent_map: dict[ast.AST, ast.AST]) -> bool:
    current = parent_map.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return False
        current = parent_map.get(current)
    return True
