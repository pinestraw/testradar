from __future__ import annotations

import ast
import textwrap

import pytest

import testradar.parse as parse_module
from testradar.parse import parse_python_source


def test_parse_python_source_handles_legacy_multiple_exception_syntax():
    tree = parse_python_source(
        textwrap.dedent(
            """
            def demo():
                try:
                    return 1
                except TypeError, ValueError:
                    return 0
            """,
        ),
        filename="demo.py",
    )

    handler = ast.dump(tree, include_attributes=False)
    assert "ExceptHandler(type=Tuple" in handler


def test_parse_python_source_handles_legacy_exception_binding():
    tree = parse_python_source(
        textwrap.dedent(
            """
            def demo():
                try:
                    return 1
                except RuntimeError, exc:
                    return str(exc)
            """,
        ),
        filename="demo.py",
    )

    handler = next(node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler))
    assert isinstance(handler.type, ast.Name)
    assert handler.type.id == "RuntimeError"
    assert handler.name == "exc"


def test_parse_python_source_preserves_unrelated_syntax_errors():
    try:
        parse_python_source("def broken(:\n", filename="broken.py")
    except SyntaxError as exc:
        assert "invalid syntax" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("expected SyntaxError")


def test_parse_python_source_reraises_when_sanitizer_returns_same_source(monkeypatch):
    monkeypatch.setattr(parse_module, "_sanitize_legacy_except_syntax", lambda source: source)

    with pytest.raises(SyntaxError) as exc_info:
        parse_python_source(
            textwrap.dedent(
                """
                def demo():
                    try:
                        return 1
                    except ValueError, TypeError:
                        return 0
                """,
            ),
            filename="demo.py",
        )
    assert exc_info.value.filename == "demo.py"
    assert exc_info.value.lineno == 5


def test_parse_python_source_reraises_original_when_sanitized_code_is_still_invalid(monkeypatch):
    monkeypatch.setattr(parse_module, "_sanitize_legacy_except_syntax", lambda _source: "def broken(:\n")

    with pytest.raises(SyntaxError) as exc_info:
        parse_python_source(
            textwrap.dedent(
                """
                def demo():
                    try:
                        return 1
                    except ValueError, TypeError:
                        return 0
                """,
            ),
            filename="demo.py",
        )
    assert exc_info.value.filename == "demo.py"
    assert exc_info.value.lineno == 5
