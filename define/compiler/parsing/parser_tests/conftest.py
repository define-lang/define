"""Shared parser fixtures for parser_tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from define.compiler.parsing import test_helpers

if TYPE_CHECKING:
    import pathlib

    from define.compiler import ast
    from define.compiler.parsing.native import native_parser


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
def native_parse_with_diagnostics() -> NativeParseWithDiagnostics:
    """Return a parse callable that uses the parser in parser.rs and returns its whole result."""
    return test_helpers.parse_with_diagnostics


@pytest.fixture
def native_parse() -> NativeParse:
    """Return a parse callable that uses the parser in parser.rs and raises its exceptions."""
    return test_helpers.parse
