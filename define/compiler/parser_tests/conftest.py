"""Shared parser fixtures for parser_tests."""

import pathlib
from typing import Protocol

import pytest

from define.compiler import parser
from define.compiler.lark import lark_standalone

_parser = parser.Parser()


class Parse(Protocol):
    """Callable that parses source, asserts no diagnostics, and returns the tree."""

    def __call__(
        self,
        source: str,
        file_path: pathlib.PurePosixPath | None = ...,
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        """Parse source and return the parse tree."""
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
    ) -> lark_standalone.Tree[lark_standalone.Token]:
        result = _parser.parse(source, file_path=file_path)
        assert result.diagnostics == []
        if result.exception is not None:
            raise result.exception
        assert result.tree is not None
        return result.tree

    return _parse
