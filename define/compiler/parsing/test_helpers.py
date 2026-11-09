"""Shared helpers for compiler tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.parsing import parser

if TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.errors import syntax_errors


def parse(source: str, file_path: str | None = None) -> ast.Program:
    """Parse source into an AST Program, which must have no diagnostics or syntax error."""
    result = parse_with_diagnostics(source, file_path)
    assert result.diagnostics == []
    assert result.syntax_error is None
    assert result.program is not None
    return result.program


def parse_syntax_error(
    source: str, file_path: str | None = None
) -> syntax_errors.DefineSyntaxError:
    """Parse source, which must end in a syntax error with no diagnostics before it, and return the syntax error."""
    result = parse_with_diagnostics(source, file_path)
    assert result.diagnostics == []
    assert result.program is None
    assert result.syntax_error is not None
    return result.syntax_error


def parse_with_diagnostics(
    source: str, file_path: str | None = None
) -> parser.ParseResult:
    """Parse source, and return the parser's result."""
    # A lone surrogate in source becomes invalid UTF-8, as it would be in a
    # file, instead of failing to encode.
    return parser.parse(source.encode(errors="surrogatepass"), file_path)
