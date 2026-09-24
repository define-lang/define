"""Encoding definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests import test_helpers

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_encoding_definition(parse: Parse):
    tree = parse("define the encoding<mv:define-lang.org:parser:/number/rational>.\n")
    assert test_helpers.get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/number/rational"
    ]
    assert test_helpers.get_tokens_by_type(tree, "DEFINE_THE_ENCODING") == [
        "define the encoding"
    ]


def test_encoding_definition_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the encoding<rational>.\n")
    assert error.value.token == "rational"
    assert error.value.line == 1
    assert error.value.column == 21


def test_encoding_definition_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/rational>\n")
    assert error.value.token == "\n"
    assert error.value.line == 1
    assert error.value.column == 47


def test_encoding_definition_disallows_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/rational> {\n}\n")
    assert error.value.token == " {"
    assert error.value.line == 1
    assert error.value.column == 47


def test_encoding_definition_disallows_potential(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        _ = parse("define the potential encoding<mv:define-lang.org:parser:/utf8>.\n")
    assert error.value.line == 1
    assert error.value.column == 1


def test_encoding_definition_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        _ = parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the encoding<mv:define-lang.org:parser:/utf8>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "define the encoding"


def test_encoding_disallowed_in_constraints(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/test> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the encoding</utf8>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 3
    assert error.value.column == 20
    assert error.value.token == "encoding<"
