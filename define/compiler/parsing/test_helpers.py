"""Shared helpers for compiler tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.parsing import parser, parser_comparison

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast

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
    """Parse source into an AST Program with the parser in parser.rs."""
    _ = parser_comparison.compare(source, file_path)
    return parser_comparison.native_parse(source, file_path)
