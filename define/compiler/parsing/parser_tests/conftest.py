"""Shared parser fixtures for parser_tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler.parsing import test_helpers

if TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.errors import syntax_errors
    from define.compiler.parsing import parser


class Parse(Protocol):
    """Callable that parses source and returns the program."""

    def __call__(
        self,
        source: str,
        file_path: str | None = ...,
    ) -> ast.Program:
        """Parse source and return the program."""
        ...


class ParseSyntaxError(Protocol):
    """Callable that parses source that ends in a syntax error and returns the syntax error."""

    def __call__(
        self,
        source: str,
        file_path: str | None = ...,
    ) -> syntax_errors.DefineSyntaxError:
        """Parse source and return its syntax error."""
        ...


class ParseWithDiagnostics(Protocol):
    """Callable that parses source and returns the parser's result."""

    def __call__(
        self,
        source: str,
        file_path: str | None = ...,
    ) -> parser.ParseResult:
        """Parse source and return the result."""
        ...


@pytest.fixture
def parse_with_diagnostics() -> ParseWithDiagnostics:
    """Return a parse callable that returns the parser's whole result."""
    return test_helpers.parse_with_diagnostics


@pytest.fixture
def parse() -> Parse:
    """Return a parse callable that returns the program of source with no diagnostics or syntax error."""
    return test_helpers.parse


@pytest.fixture
def parse_syntax_error() -> ParseSyntaxError:
    """Return a parse callable that returns the syntax error that source ends in."""
    return test_helpers.parse_syntax_error
