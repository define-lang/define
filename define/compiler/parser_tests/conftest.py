"""Shared parser fixtures for parser_tests."""

import pytest

from define.compiler import parser

_parser = parser.Parser()


@pytest.fixture
def p() -> parser.Parser:
    """Return the shared parser instance used by parser tests."""
    return _parser
