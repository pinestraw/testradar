from __future__ import annotations

import ast
import re


_LEGACY_EXCEPT_HEADER = re.compile(r"^(?P<indent>\s*)except\s+(?P<clause>.+?)(?P<suffix>\s*:\s*(?:#.*)?)$")


def parse_python_source(source: str, *, filename: str) -> ast.AST:
    try:
        return ast.parse(source, filename=filename)
    except SyntaxError as exc:
        if "multiple exception types must be parenthesized" not in str(exc):
            raise
        sanitized = _sanitize_legacy_except_syntax(source)
        if sanitized == source:
            raise
        try:
            return ast.parse(sanitized, filename=filename)
        except SyntaxError:
            raise exc


def _sanitize_legacy_except_syntax(source: str) -> str:
    rewritten_lines: list[str] = []
    changed = False
    for line in source.splitlines(keepends=True):
        rewritten = _rewrite_legacy_except_line(line)
        if rewritten != line:
            changed = True
        rewritten_lines.append(rewritten)
    if not changed:
        return source
    return "".join(rewritten_lines)


def _rewrite_legacy_except_line(line: str) -> str:
    newline = ""
    body = line
    if body.endswith("\r\n"):
        body = body[:-2]
        newline = "\r\n"
    elif body.endswith("\n"):
        body = body[:-1]
        newline = "\n"

    match = _LEGACY_EXCEPT_HEADER.match(body)
    if match is None:
        return line

    clause = match.group("clause")
    if " as " in clause or "," not in clause:
        return line

    parts = [part.strip() for part in _split_top_level_commas(clause)]
    if len(parts) < 2 or any(not part for part in parts):
        return line

    if len(parts) == 2 and _looks_like_exception_binding_target(parts[1]):
        normalized_clause = f"{parts[0]} as {parts[1]}"
    else:
        normalized_clause = f"({', '.join(parts)})"
    return f"{match.group('indent')}except {normalized_clause}{match.group('suffix')}{newline}"


def _split_top_level_commas(clause: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(clause):
        if quote is not None:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char in "([{":
            depth += 1
            continue
        if char in ")]}":
            depth = max(depth - 1, 0)
            continue
        if char == "," and depth == 0:
            parts.append(clause[start:index])
            start = index + 1
    parts.append(clause[start:])
    return parts


def _looks_like_exception_binding_target(value: str) -> bool:
    if not value.isidentifier():
        return False
    first = value[0]
    return first.islower() or first == "_"
