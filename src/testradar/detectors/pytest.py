from __future__ import annotations

import ast
from pathlib import Path

from testradar.models import ImportRequest


class PytestPluginDetector:
    name = "pytest-plugin-strings"

    def detect(
        self,
        *,
        tree: ast.AST,
        path: Path,
        module: str | None,
    ) -> tuple[ImportRequest, ...]:
        results: list[ImportRequest] = []
        for node in getattr(tree, "body", []):
            if isinstance(node, ast.Assign):
                if any(isinstance(target, ast.Name) and target.id == "pytest_plugins" for target in node.targets):
                    results.extend(_extract_plugin_requests(node.value))
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                if isinstance(target, ast.Name) and target.id == "pytest_plugins" and node.value is not None:
                    results.extend(_extract_plugin_requests(node.value))
        return tuple(results)


def _extract_plugin_requests(node: ast.AST) -> list[ImportRequest]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [ImportRequest(module=node.value)]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        results: list[ImportRequest] = []
        for element in node.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                results.append(ImportRequest(module=element.value))
        return results
    return []
