from __future__ import annotations

import ast
from pathlib import Path

from testradar.models import HunkRange, NodeSpan


def select_changed_tests(path: Path, relative_path: str, hunks: tuple[HunkRange, ...]) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative_path)
    spans = _collect_node_spans(tree, relative_path)
    if not spans:
        return [relative_path]

    selected: set[str] = set()
    for hunk in hunks:
        span = _match_hunk(spans, hunk)
        if span is None:
            return [relative_path]
        if span.has_decorators or span.has_parametrize:
            return [relative_path]
        selected.add(span.nodeid)

    return sorted(selected) or [relative_path]


def _collect_node_spans(tree: ast.AST, relative_path: str) -> list[NodeSpan]:
    spans: list[NodeSpan] = []
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            spans.append(_function_span(relative_path, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith(
                    "test_",
                ):
                    spans.append(_method_span(relative_path, node, child))
    return spans


def _function_span(relative_path: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> NodeSpan:
    start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
    return NodeSpan(
        nodeid=f"{relative_path}::{node.name}",
        start=start,
        end=node.end_lineno or node.lineno,
        has_parametrize=_has_parametrize(node),
        has_decorators=bool(node.decorator_list),
    )


def _method_span(
    relative_path: str,
    parent: ast.ClassDef,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> NodeSpan:
    start = min([node.lineno, *[decorator.lineno for decorator in node.decorator_list]])
    return NodeSpan(
        nodeid=f"{relative_path}::{parent.name}::{node.name}",
        start=start,
        end=node.end_lineno or node.lineno,
        has_parametrize=_has_parametrize(node),
        has_decorators=bool(node.decorator_list),
    )


def _has_parametrize(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        dotted = _call_name(decorator.func) if isinstance(decorator, ast.Call) else _call_name(decorator)
        if dotted and dotted.endswith("parametrize"):
            return True
    return False


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _match_hunk(spans: list[NodeSpan], hunk: HunkRange) -> NodeSpan | None:
    matching = [span for span in spans if hunk.overlaps(span.start, span.end)]
    if len(matching) != 1:
        return None
    span = matching[0]
    if hunk.start < span.start or hunk.end > span.end:
        return None
    return span
