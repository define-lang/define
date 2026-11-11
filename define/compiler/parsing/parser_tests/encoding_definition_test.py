"""Encoding definition parser tests."""

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


def test_encoding_definition(parse: Parse):
    program = parse("define the encoding<mv:define-lang.org:parser:/number/natural>.\n")
    [definition] = program.definitions
    assert isinstance(definition, ast.EncodingDefinition)
    assert definition.typed_name.name_type == name_types.NameType.ENCODING
    assert definition.typed_name.name_content.path.name == "/number/natural"
    assert definition.typed_name.location == rendering.SourceLocation(
        line=1, column=12, end_line=1, end_column=62
    )
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )


def test_encoding_definition_requires_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the encoding<rational>.\n")
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 1
    assert error.location.column == 21
    assert error.location.end_line == 1
    assert error.location.end_column == 28


def test_encoding_definition_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics("define the encoding<standard:/number/natural>\n")
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=46, end_line=1, end_column=46
            )
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.EncodingDefinition)
    assert definition.typed_name.name_content.path.name == "/number/natural"
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=1, end_column=45
    )


def test_encoding_definition_disallows_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the encoding<standard:/number/natural> {\n}\n")
    assert isinstance(error, syntax_errors.MissingTerminator)
    assert error.location.line == 1
    assert error.location.column == 46
    assert error.location.end_line == 1
    assert error.location.end_column == 46


def test_encoding_definition_disallows_potential(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential encoding<mv:define-lang.org:parser:/utf8>.\n"
    )
    assert isinstance(error, syntax_errors.ExpectedGlobalDefinition)
    assert error.location.line == 1
    assert error.location.column == 1
    assert error.location.end_line == 1
    assert error.location.end_column == 63


def test_encoding_definition_disallows_local_context(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/test> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + "        define the encoding<mv:define-lang.org:parser:/utf8>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidActionStatementsBlock)
    assert error.location.line == 5
    assert error.location.column == 9
    assert error.location.end_line == 5
    assert error.location.end_column == 61


def test_encoding_in_quality_assignments(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/test> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the encoding</utf8>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/test>"
    )
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == rendering.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )
    typed_name = quality_assignment.typed_global_name
    assert typed_name.name_type == name_types.NameType.ENCODING
    assert typed_name.location == rendering.SourceLocation(
        line=3, column=20, end_line=3, end_column=34
    )
    assert typed_name.name_content.fqun is None
    assert typed_name.name_content.path.name == "/utf8"
    assert typed_name.name_content.path.location == rendering.SourceLocation(
        line=3, column=29, end_line=3, end_column=33
    )
