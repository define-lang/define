"""Potential literal definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


def test_potential_literal_definition(parse: Parse):
    program = parse(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal_text>.\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert definition.typed_name.name_type == name_types.NameType.LITERAL
    assert definition.typed_name.name_content.path.name == "/decimal"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=64
    )
    encoding = definition.encoding
    assert encoding.name_type == name_types.NameType.ENCODING
    assert encoding.name_content.fqun is None
    assert encoding.name_content.path.name == "/decimal_text"
    assert encoding.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=38
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=3, end_column=1
    )


def test_comments_and_blank_lines(parse: Parse):
    program = parse(
        "define the potential literal<mv:define-lang.org:parser:/decimal> { # comment\n"
        + "\n"
        + "    # comment\n"
        + "    it has the encoding<standard:/decimal_text>. # comment\n"
        + "\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert definition.encoding.name_content.path.name == "/decimal_text"
    assert definition.encoding.location == ast.SourceLocation(
        line=4, column=16, end_line=4, end_column=47
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=6, end_column=1
    )


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse("define the potential literal<decimal> {\n}\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 30
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 36


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        _ = parse("define the potential literal<mv:define-lang.org:parser:/decimal>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 65
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 65


def test_requires_encoding_quality_assignment(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialLiteralDefinitionBlock
    ) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 1


def test_requires_encoding_type(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialLiteralDefinitionBlock
    ) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the value</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 16
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 20


def test_encoding_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding<decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 25
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 31


def test_encoding_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal>\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=2, column=34, end_line=2, end_column=34)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert definition.encoding.name_content.path.name == "/decimal"
    assert definition.encoding.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=33
    )


def test_disallows_multiple_encodings(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>.\n"
            + "    it has the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 34


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
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 74


def test_disallows_particle_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedQualityAssignmentNameType) as error:
        _ = parse(
            "define the potential position<mv:define-lang.org:parser:/test> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the literal</decimal>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 26


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as error:
        _ = parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it also assigns the literal</decimal>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 25
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 31


def test_statement_that_is_not_an_encoding_quality_assignment(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialLiteralDefinitionBlock
    ) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it is a literal.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 20
