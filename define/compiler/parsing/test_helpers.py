"""Shared helpers for compiler tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.parsing import parser, parser_comparison

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast
    from define.compiler.parsing import native_parser

_PARSER = parser.Parser()


def parse_and_transform(
    source: str, file_path: PurePosixPath | None = None
) -> ast.Program:
    """Parse and transform source into an AST Program."""
    _ = parser_comparison.compare(source, file_path)
    result = _PARSER.parse_and_transform(source, file_path=file_path)
    assert result.diagnostics == []
    assert result.exception is None
    assert result.program is not None
    return result.program


def parse(source: str, file_path: PurePosixPath | None = None) -> ast.Program:
    """Parse source into an AST Program with the parser in parser.rs, which must report no diagnostics."""
    _ = parser_comparison.compare(source, file_path)
    return _program(parser_comparison.native_parse(source, file_path))


def parse_where_lark_is_wrong(
    source: str, file_path: PurePosixPath | None = None
) -> ast.Program:
    """Parse source like `parse`, for a source the Lark parser accepts by mistake."""
    return _program(
        parser_comparison.native_parse_where_lark_is_wrong(source, file_path)
    )


def parse_with_diagnostics(
    source: str, file_path: PurePosixPath | None = None
) -> native_parser.ParseResult:
    """Parse source with the parser in parser.rs, and return its result."""
    _ = parser_comparison.compare(source, file_path)
    return parser_comparison.native_parse(source, file_path)


def _program(result: native_parser.ParseResult) -> ast.Program:
    assert result.diagnostics == []
    if result.exception is not None:
        raise result.exception
    assert result.program is not None
    return result.program
