"""Shared parser fixtures for parser_tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler.parsing import parser, parser_comparison, test_helpers

if TYPE_CHECKING:
    import pathlib

    import lark_cython

    from define.compiler import ast
    from define.compiler.parsing import native_parser
    from define.compiler.parsing.lark import lark_standalone

_parser = parser.Parser()


class Parse(Protocol):
    """Callable that parses source, asserts no diagnostics, and returns the tree."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> lark_standalone.Tree[lark_cython.Token]:
        """Parse source and return the parse tree."""
        ...


class NativeParse(Protocol):
    """Callable that parses source with the parser in parser.rs and returns the program."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> ast.Program:
        """Parse source and return the program."""
        ...


class NativeParseWithDiagnostics(Protocol):
    """Callable that parses source with the parser in parser.rs and returns its result."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> native_parser.ParseResult:
        """Parse source and return the result."""
        ...


@pytest.fixture
def p() -> parser.Parser:
    """Return the shared parser instance used by parser tests."""
    return _parser


@pytest.fixture
def parse() -> Parse:
    """Return a parse callable that asserts no diagnostics and raises exceptions."""

    def _parse(
        source: str, file_path: pathlib.PurePosixPath | None = None
    ) -> lark_standalone.Tree[lark_cython.Token]:
        _ = parser_comparison.compare(source, file_path)
        result = _parser.parse(source, file_path=file_path)
        assert result.diagnostics == []
        if result.exception is not None:
            raise result.exception
        assert result.tree is not None
        return result.tree

    return _parse


@pytest.fixture
def native_parse_lark_wrong() -> NativeParse:
    """Return a parse callable that uses the parser in parser.rs, for sources the Lark parser accepts by mistake."""
    return test_helpers.parse_where_lark_is_wrong


@pytest.fixture
def native_parse_with_diagnostics() -> NativeParseWithDiagnostics:
    """Return a parse callable that uses the parser in parser.rs and returns its whole result."""
    return test_helpers.parse_with_diagnostics


@pytest.fixture
def native_parse() -> NativeParse:
    """Return a parse callable that uses the parser in parser.rs and raises its exceptions."""
    return test_helpers.parse
