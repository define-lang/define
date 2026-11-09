# pyright: reportUnusedCallResult=false
"""Logical operation definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, syntax_errors
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
        ParseWithDiagnostics,
    )


def _only_logical_operation(program: ast.Program) -> ast.LogicalOperationDefinition:
    [definition] = program.definitions
    assert isinstance(definition, ast.LogicalOperationDefinition)
    return definition


def test_logical_operation_definition(parse: Parse):
    definition = _only_logical_operation(
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is read.\n"
            + "    }\n"
            + "    define the view<b> {\n"
            + "        it is read.\n"
            + "    }\n"
            + "    define the view<result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    )
    assert definition.typed_name.name_type == name_types.NameType.LOGICAL_OPERATION
    assert definition.typed_name.name_content.path.name == "/add"
    assert definition.typed_name.location == rendering.SourceLocation(
        line=1, column=12, end_line=1, end_column=60
    )
    [a, b, result] = definition.views
    assert a.typed_name.name_type == name_types.NameType.VIEW
    assert a.typed_name.name_content.name == "a"
    assert a.typed_name.location == rendering.SourceLocation(
        line=2, column=16, end_line=2, end_column=22
    )
    assert a.is_input
    assert not a.is_output
    assert a.location == rendering.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )
    assert b.typed_name.name_content.name == "b"
    assert b.is_input
    assert not b.is_output
    assert b.location == rendering.SourceLocation(
        line=5, column=5, end_line=7, end_column=5
    )
    assert result.typed_name.name_content.name == "result"
    assert not result.is_input
    assert result.is_output
    assert result.location == rendering.SourceLocation(
        line=8, column=5, end_line=10, end_column=5
    )
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=11, end_column=1
    )


def test_view_disallows_read_and_written(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/increment> {\n"
        + "    define the view<number> {\n"
        + "        it is read.\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraLogicalOperationViewDirectionStatement)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 22


def test_view_disallows_read_and_written_after_comment(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/increment> {\n"
        + "    define the view<number> {\n"
        + "        it is read. # comment\n"
        + "\n"
        + "        # comment\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraLogicalOperationViewDirectionStatement)
    assert error.location.line == 6
    assert error.location.column == 9
    assert error.location.end_line == 6
    assert error.location.end_column == 22


def test_comments_and_blank_lines(parse: Parse):
    definition = _only_logical_operation(
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> { # comment\n"
            + "\n"
            + "    # comment\n"
            + "    define the view<a> { # comment\n"
            + "\n"
            + "        it is read. # comment\n"
            + "\n"
            + "    } # comment\n"
            + "\n"
            + "    define the view<result> { # comment\n"
            + "        it is written. # comment\n"
            + "    } # comment\n"
            + "\n"
            + "} # comment\n"
        )
    )
    [a, result] = definition.views
    assert a.is_input
    assert not a.is_output
    assert a.location == rendering.SourceLocation(
        line=4, column=5, end_line=8, end_column=5
    )
    assert not result.is_input
    assert result.is_output
    assert result.location == rendering.SourceLocation(
        line=10, column=5, end_line=12, end_column=5
    )
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=14, end_column=1
    )


def test_between_other_definitions(parse: Parse):
    program = parse(
        "define the encoding<mv:define-lang.org:parser:/decimal>.\n"
        + "define the logical_operation<mv:define-lang.org:parser:/negate> {\n"
        + "    define the view<result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
        + "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    [encoding, logical_operation, operation] = program.definitions
    assert isinstance(encoding, ast.EncodingDefinition)
    assert isinstance(logical_operation, ast.LogicalOperationDefinition)
    assert logical_operation.typed_name.name_content.path.name == "/negate"
    assert logical_operation.location == rendering.SourceLocation(
        line=2, column=1, end_line=6, end_column=1
    )
    assert isinstance(operation, ast.ValueOperationDefinition)


def test_read_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is read\n"
        + "    }\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=3, column=19, end_line=3, end_column=19
            )
        )
    ]
    assert result.program is not None
    [view] = _only_logical_operation(result.program).views
    assert view.is_input
    assert not view.is_output


def test_requires_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<add> {\n"
        + "    define the view<result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 1
    assert error.location.column == 30
    assert error.location.end_line == 1
    assert error.location.end_column == 32


def test_requires_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add>.\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenBrace)
    assert error.location.line == 1
    assert error.location.column == 61
    assert error.location.end_line == 1
    assert error.location.end_column == 61


def test_requires_view_definition(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingLogicalOperationViewDefinition)
    assert error.location.line == 2
    assert error.location.column == 1
    assert error.location.end_line == 2
    assert error.location.end_column == 1


def test_requires_view_definition_before_end_of_source(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
    )
    assert isinstance(error, syntax_errors.MissingLogicalOperationViewDefinition)
    assert error.location.line == 1
    assert error.location.column == 63
    assert error.location.end_line == 1
    assert error.location.end_column == 63


def test_disallows_operation_statements_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidLogicalOperationDefinitionBlock)
    assert error.location.line == 5
    assert error.location.column == 5
    assert error.location.end_line == 5
    assert error.location.end_column == 13


def test_disallows_local_position_definition(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the position<p>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidLogicalOperationDefinitionBlock)
    assert error.location.line == 2
    assert error.location.column == 5
    assert error.location.end_line == 2
    assert error.location.end_column == 27


def test_control_character_in_view_definition(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the \x00view<result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ControlCharacterError)
    assert error.escaped_char == "\\0"
    assert error.location.line == 2
    assert error.location.column == 16
    assert error.location.end_line == 2
    assert error.location.end_column == 16


def test_extra_space_in_view_definition(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the  view<result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 2
    assert error.location.column == 15
    assert error.location.end_line == 2
    assert error.location.end_column == 16


def test_view_requires_local_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view</result> {\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.GlobalNameWhereLocalNameExpected)
    assert error.location.line == 2
    assert error.location.column == 21
    assert error.location.end_line == 2
    assert error.location.end_column == 27


def test_view_requires_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenBrace)
    assert error.location.line == 2
    assert error.location.column == 28
    assert error.location.end_line == 2
    assert error.location.end_column == 28


def test_view_requires_direction_statement(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        error, syntax_errors.MissingLogicalOperationViewDirectionStatement
    )
    assert error.location.line == 3
    assert error.location.column == 5
    assert error.location.end_line == 3
    assert error.location.end_column == 5


def test_view_requires_direction_statement_instead_of_quality_assignment_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(
        error, syntax_errors.MissingLogicalOperationViewDirectionStatement
    )
    assert error.location.line == 3
    assert error.location.column == 9
    assert error.location.end_line == 3
    assert error.location.end_column == 45


def test_view_requires_direction_statement_before_end_of_source(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
    )
    assert isinstance(
        error, syntax_errors.MissingLogicalOperationViewDirectionStatement
    )
    assert error.location.line == 2
    assert error.location.column == 30
    assert error.location.end_line == 2
    assert error.location.end_column == 30


def test_view_extra_space_in_direction_statement(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
        + "        it  is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 3
    assert error.location.column == 11
    assert error.location.end_line == 3
    assert error.location.end_column == 12


def test_view_disallows_quality_assignment_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<result> {\n"
        + "        it is written.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidLogicalOperationViewDefinitionBlock)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 45


def test_view_control_character_in_statement_after_direction_statement(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is read.\n"
        + "        it is \x00written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ControlCharacterError)
    assert error.escaped_char == "\\0"
    assert error.location.line == 4
    assert error.location.column == 15
    assert error.location.end_line == 4
    assert error.location.end_column == 15


def test_view_extra_space_in_statement_after_direction_statement(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is read.\n"
        + "        it  is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 4
    assert error.location.column == 11
    assert error.location.end_line == 4
    assert error.location.end_column == 12


def test_view_disallows_written_and_read(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is written.\n"
        + "        it is read.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraLogicalOperationViewDirectionStatement)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 19


def test_view_disallows_repeated_read(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is read.\n"
        + "        it is read.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraLogicalOperationViewDirectionStatement)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 19


def test_view_disallows_repeated_written(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is written.\n"
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraLogicalOperationViewDirectionStatement)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 22


def test_view_requires_close_brace(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is written.\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseBrace)
    assert error.location.line == 2
    assert error.location.column == 5
    assert error.location.end_line == 2
    assert error.location.end_column == 24


def test_requires_close_brace(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<a> {\n"
        + "        it is written.\n"
        + "    }\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseBrace)
    assert error.location.line == 1
    assert error.location.column == 1
    assert error.location.end_line == 1
    assert error.location.end_column == 62


def test_disallows_local_context(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/test> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + "        define the logical_operation<mv:define-lang.org:parser:/add> {\n"
        + "            define the view<result> {\n"
        + "                it is written.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidActionStatementsBlock)
    assert error.location.line == 5
    assert error.location.column == 9
    assert error.location.end_line == 5
    assert error.location.end_column == 70
