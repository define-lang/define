"""Potential literal definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, syntax_errors

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
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
    assert definition.typed_name.location == rendering.SourceLocation(
        line=1, column=22, end_line=1, end_column=64
    )
    encoding = definition.encoding
    assert encoding.name_type == name_types.NameType.ENCODING
    assert encoding.name_content.fqun is None
    assert encoding.name_content.path.name == "/decimal_text"
    assert encoding.location == rendering.SourceLocation(
        line=2, column=16, end_line=2, end_column=38
    )
    assert definition.location == rendering.SourceLocation(
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
    assert definition.encoding.location == rendering.SourceLocation(
        line=4, column=16, end_line=4, end_column=47
    )
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=6, end_column=1
    )


def test_requires_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the potential literal<decimal> {\n}\n")
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 1
    assert error.location.column == 30
    assert error.location.end_line == 1
    assert error.location.end_column == 36


def test_requires_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal>.\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenBrace)
    assert error.location.line == 1
    assert error.location.column == 65
    assert error.location.end_line == 1
    assert error.location.end_column == 65


def test_requires_encoding_quality_assignment(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n" + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidPotentialLiteralDefinitionBlock)
    assert error.location.line == 2
    assert error.location.column == 1
    assert error.location.end_line == 2
    assert error.location.end_column == 1


def test_requires_encoding_type(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the value</decimal>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidPotentialLiteralDefinitionBlock)
    assert error.location.line == 2
    assert error.location.column == 16
    assert error.location.end_line == 2
    assert error.location.end_column == 20


def test_encoding_requires_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding<decimal>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 2
    assert error.location.column == 25
    assert error.location.end_line == 2
    assert error.location.end_column == 31


def test_encoding_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal>\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=34, end_line=2, end_column=34
            )
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PotentialLiteralDefinition)
    assert definition.encoding.name_content.path.name == "/decimal"
    assert definition.encoding.location == rendering.SourceLocation(
        line=2, column=16, end_line=2, end_column=33
    )


def test_disallows_multiple_encodings(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal>.\n"
        + "    it has the encoding</decimal>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseBrace)
    assert error.location.line == 3
    assert error.location.column == 5
    assert error.location.end_line == 3
    assert error.location.end_column == 34


def test_disallows_local_context(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
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
    assert isinstance(error, syntax_errors.InvalidActionStatementsBlock)
    assert error.location.line == 5
    assert error.location.column == 9
    assert error.location.end_line == 5
    assert error.location.end_column == 74


def test_disallows_particle_quality_assignment(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/test> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the literal</decimal>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedQualityAssignmentNameType)
    assert error.location.line == 3
    assert error.location.column == 20
    assert error.location.end_line == 3
    assert error.location.end_column == 26


def test_disallows_quality_implication(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/test> {\n"
        + "    it also assigns the literal</decimal>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 2
    assert error.location.column == 25
    assert error.location.end_line == 2
    assert error.location.end_column == 31


def test_statement_that_is_not_an_encoding_quality_assignment(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it is a literal.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidPotentialLiteralDefinitionBlock)
    assert error.location.line == 2
    assert error.location.column == 5
    assert error.location.end_line == 2
    assert error.location.end_column == 20
