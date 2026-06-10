from __future__ import annotations

import ast
from pathlib import Path

from testradar.models import ImportRequest


class GenericDynamicImportDetector:
    name = "generic-dynamic-imports"

    def detect(
        self,
        *,
        tree: ast.AST,
        path: Path,
        module: str | None,
    ) -> tuple[ImportRequest, ...]:
        results: list[ImportRequest] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            dotted_name = _call_name(node.func)
            if dotted_name not in {"importlib.import_module", "import_module", "__import__"}:
                continue
            if not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                results.append(ImportRequest(module=arg.value))
        return tuple(results)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None
