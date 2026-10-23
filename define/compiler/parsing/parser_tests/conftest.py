"""Shared parser fixtures for parser_tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler.parsing import test_helpers

if TYPE_CHECKING:
    import pathlib

    from define.compiler import ast
    from define.compiler.parsing import parser


class Parse(Protocol):
    """Callable that parses source and returns the program."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> ast.Program:
        """Parse source and return the program."""
        ...


class ParseWithDiagnostics(Protocol):
    """Callable that parses source and returns the parser's result."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> parser.ParseResult:
        """Parse source and return the result."""
        ...


@pytest.fixture
def parse_with_diagnostics() -> ParseWithDiagnostics:
    """Return a parse callable that returns the parser's whole result."""
    return test_helpers.parse_with_diagnostics


@pytest.fixture
def parse() -> Parse:
    """Return a parse callable that raises the parser's exceptions."""
    return test_helpers.parse
