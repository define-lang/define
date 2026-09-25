"""Potential literal definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests import test_helpers

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_potential_literal_definition(parse: Parse):
    tree = parse(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal_text>.\n"
        + "}\n"
    )
    assert test_helpers.get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/decimal",
        "/decimal_text",
    ]
    assert test_helpers.get_tokens_by_type(tree, "DEFINE_THE_POTENTIAL_LITERAL") == [
        "define the potential literal"
    ]


def test_comments_and_blank_lines(parse: Parse):
    _ = parse(
        "define the potential literal<mv:define-lang.org:parser:/decimal> { # comment\n"
        + "\n"
        + "    # comment\n"
        + "    it has the encoding<standard:/decimal_text>. # comment\n"
        + "\n"
        + "}\n"
    )


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the potential literal<decimal> {\n}\n")
    assert error.value.line == 1
    assert error.value.column == 30
    assert error.value.token == "decimal"


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        _ = parse("define the potential literal<mv:define-lang.org:parser:/decimal>.\n")
    assert error.value.line == 1
    assert error.value.column == 65
    assert error.value.token == "."


def test_requires_encoding_constraint(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialLiteralDefinitionBlock
    ) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 1
    assert error.value.token == "}"


def test_requires_encoding_type(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialLiteralDefinitionBlock
    ) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the value</decimal>.\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 16
    assert error.value.token == "value"


def test_encoding_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding<decimal>.\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 25
    assert error.value.token == "decimal"


def test_encoding_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 34
    assert error.value.token == "\n"


def test_disallows_multiple_encodings(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>.\n"
            + "    it has the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.line == 3
    assert error.value.column == 5
    assert error.value.token == "it has the"


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        _ = parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "            it has the encoding</decimal>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 5
    assert error.value.column == 9
    assert error.value.token == "define the potential literal"


def test_disallows_particle_constraint(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/test> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the literal</decimal>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.line == 3
    assert error.value.column == 20
    assert error.value.token == "literal"


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/test> {\n"
            + "    it also assigns the literal</decimal>.\n"
            + "}\n"
        )
    assert error.value.line == 2
    assert error.value.column == 25
    assert error.value.token == "literal"
