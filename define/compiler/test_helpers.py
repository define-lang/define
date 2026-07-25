"""Shared helpers for compiler tests."""

from pathlib import PurePosixPath

from define.compiler import ast, parser

_PARSER = parser.Parser()


def parse_and_transform(
    source: str, file_path: PurePosixPath | None = None
) -> ast.Program:
    """Parse and transform source into an AST Program."""
    result = _PARSER.parse_and_transform(source, file_path=file_path)
    assert result.diagnostics == []
    assert result.exception is None
    assert result.program is not None
    return result.program
