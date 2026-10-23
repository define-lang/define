"""Shared helpers for compiler tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.parsing.native import native_parser

if TYPE_CHECKING:
    from pathlib import PurePosixPath

    from define.compiler import ast


def parse(source: str, file_path: PurePosixPath | None = None) -> ast.Program:
    """Parse source into an AST Program, which must have no diagnostics."""
    result = parse_with_diagnostics(source, file_path)
    assert result.diagnostics == []
    if result.exception is not None:
        raise result.exception
    assert result.program is not None
    return result.program


def parse_with_diagnostics(
    source: str, file_path: PurePosixPath | None = None
) -> native_parser.ParseResult:
    """Parse source, and return the parser's result."""
    # A lone surrogate in source becomes invalid UTF-8, as it would be in a
    # file, instead of failing to encode.
    return native_parser.parse(source.encode(errors="surrogatepass"), file_path)
