"""Encoding definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests import test_helpers

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_encoding_definition(parse: Parse):
    tree = parse("define the encoding<mv:define-lang.org:parser:/number/natural>.\n")
    assert test_helpers.get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/number/natural"
    ]
    assert test_helpers.get_tokens_by_type(tree, "DEFINE_THE_ENCODING") == [
        "define the encoding"
    ]


def test_encoding_definition_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the encoding<rational>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 21
    assert error.value.location.end_column == 29


def test_encoding_definition_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/natural>\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 46
    assert error.value.location.end_column == 46


def test_encoding_definition_disallows_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse("define the encoding<standard:/number/natural> {\n}\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 46
    assert error.value.location.end_column == 48


def test_encoding_definition_disallows_potential(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        _ = parse("define the potential encoding<mv:define-lang.org:parser:/utf8>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_column == 7


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
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_column == 28


def test_encoding_in_constraints(parse: Parse):
    tree = parse(
        "define the potential position<mv:define-lang.org:parser:/test> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the encoding</utf8>.\n"
        + "    }\n"
        + "}\n"
    )
    assert test_helpers.get_tokens_by_type(tree, "ENCODING") == ["encoding"]
    assert test_helpers.get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/test",
        "/utf8",
    ]
