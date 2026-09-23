"""Value type definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests import test_helpers

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_value_definition(parse: Parse):
    tree = parse(
        "define the potential value<mv:define-lang.org:parser:/number/rational>.\n"
    )
    assert test_helpers.get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/number/rational"
    ]
    assert test_helpers.get_tokens_by_type(tree, "DEFINE_THE_POTENTIAL_VALUE") == [
        "define the potential value"
    ]


def test_value_definition_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the potential value<rational>.\n")
    assert error.value.token == "rational"
    assert error.value.line == 1
    assert error.value.column == 28


def test_value_definition_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the potential value<standard:/number/rational>\n")
    assert error.value.token == "\n"
    assert error.value.line == 1
    assert error.value.column == 54


def test_value_definition_disallows_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the potential value<standard:/number/rational> {\n}\n")
    assert error.value.token == " {"
    assert error.value.line == 1
    assert error.value.column == 54
