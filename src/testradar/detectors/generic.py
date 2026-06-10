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
        handled_calls: set[int] = set()
        assigned_modules: dict[str, tuple[str, int, bool]] = {}
        assigned_attrs: dict[str, set[str]] = {}
        parent_map = _build_parent_map(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                imported = _imported_module_from_expr(node.value)
                if imported is None:
                    continue
                module_name, call_node = imported
                assigned_modules[node.targets[0].id] = (module_name, id(call_node), _is_eager_node(node, parent_map))
                handled_calls.add(id(call_node))
                continue
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                imported = _imported_module_from_expr(node.value)
                if imported is None:
                    continue
                module_name, call_node = imported
                assigned_modules[node.target.id] = (module_name, id(call_node), _is_eager_node(node, parent_map))
                handled_calls.add(id(call_node))
                continue
            if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
                continue

            imported = _imported_module_from_expr(node.value)
            if imported is not None:
                module_name, call_node = imported
                results.append(
                    ImportRequest(
                        module=module_name,
                        names=(node.attr,),
                        is_from=True,
                        is_eager=_is_eager_node(node, parent_map),
                    ),
                )
                handled_calls.add(id(call_node))
                continue

            if isinstance(node.value, ast.Name) and node.value.id in assigned_modules:
                _module_name, call_id, _is_eager = assigned_modules[node.value.id]
                assigned_attrs.setdefault(node.value.id, set()).add(node.attr)
                handled_calls.add(call_id)

        for variable_name, (module_name, call_id, is_eager) in assigned_modules.items():
            attrs = tuple(sorted(assigned_attrs.get(variable_name, ())))
            if attrs:
                results.append(
                    ImportRequest(
                        module=module_name,
                        names=attrs,
                        is_from=True,
                        is_eager=is_eager,
                    ),
                )
                continue
            handled_calls.add(call_id)
            results.append(ImportRequest(module=module_name, is_eager=is_eager))

        for node in ast.walk(tree):
            imported = _imported_module_from_call(node)
            if imported is None:
                continue
            module_name, call_node = imported
            if id(call_node) in handled_calls:
                continue
            results.append(ImportRequest(module=module_name, is_eager=_is_eager_node(call_node, parent_map)))
        return tuple(results)


def _imported_module_from_expr(node: ast.expr | None) -> tuple[str, ast.Call] | None:
    if node is None:
        return None
    direct = _imported_module_from_call(node)
    if direct is not None:
        return direct
    if not isinstance(node, ast.Call):
        return None
    dotted_name = _call_name(node.func)
    if dotted_name not in {"cast", "typing.cast"}:
        return None
    if len(node.args) < 2:
        return None
    wrapped = node.args[1]
    if not isinstance(wrapped, ast.expr):
        return None
    return _imported_module_from_expr(wrapped)


def _imported_module_from_call(node: ast.AST) -> tuple[str, ast.Call] | None:
    if not isinstance(node, ast.Call):
        return None
    dotted_name = _call_name(node.func)
    if dotted_name not in {"importlib.import_module", "import_module", "__import__"}:
        return None
    if not node.args:
        return None
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value, node
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

