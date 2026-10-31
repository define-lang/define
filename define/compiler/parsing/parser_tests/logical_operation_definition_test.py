# pyright: reportUnusedCallResult=false
"""Logical operation definition parser tests."""

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
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=12, end_line=1, end_column=60
    )
    [a, b, result] = definition.views
    assert a.typed_name.name_type == name_types.NameType.VIEW
    assert a.typed_name.name_content.name == "a"
    assert a.typed_name.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=22
    )
    assert a.is_input
    assert not a.is_output
    assert a.location == ast.SourceLocation(line=2, column=5, end_line=4, end_column=5)
    assert b.typed_name.name_content.name == "b"
    assert b.is_input
    assert not b.is_output
    assert b.location == ast.SourceLocation(line=5, column=5, end_line=7, end_column=5)
    assert result.typed_name.name_content.name == "result"
    assert not result.is_input
    assert result.is_output
    assert result.location == ast.SourceLocation(
        line=8, column=5, end_line=10, end_column=5
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=11, end_column=1
    )


def test_read_and_written_view(parse: Parse):
    definition = _only_logical_operation(
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/increment> {\n"
            + "    define the view<number> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    )
    [view] = definition.views
    assert view.is_input
    assert view.is_output
    assert view.location == ast.SourceLocation(
        line=2, column=5, end_line=5, end_column=5
    )


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
            + "        it is written. # comment\n"
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
    assert a.is_output
    assert a.location == ast.SourceLocation(line=4, column=5, end_line=10, end_column=5)
    assert not result.is_input
    assert result.is_output
    assert result.location == ast.SourceLocation(
        line=12, column=5, end_line=14, end_column=5
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=16, end_column=1
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
    assert logical_operation.location == ast.SourceLocation(
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
        + "        it is written.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=19, end_line=3, end_column=19)
        )
    ]
    assert result.program is not None
    [view] = _only_logical_operation(result.program).views
    assert view.is_input
    assert view.is_output


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the logical_operation<add> {\n"
            + "    define the view<result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 30
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 32


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the logical_operation<mv:define-lang.org:parser:/add>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 61
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 61


def test_requires_view_definition(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLogicalOperationViewDefinition
    ) as error:
        parse("define the logical_operation<mv:define-lang.org:parser:/add> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 1


def test_requires_view_definition_before_end_of_source(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLogicalOperationViewDefinition
    ) as error:
        parse("define the logical_operation<mv:define-lang.org:parser:/add> {\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 63
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 63


def test_disallows_operation_statements_block(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidLogicalOperationDefinitionBlock
    ) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 13


def test_disallows_local_position_definition(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidLogicalOperationDefinitionBlock
    ) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the position<p>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 27


def test_control_character_in_view_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the \x00view<result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\x00"
    assert error.value.location.line == 2
    assert error.value.location.column == 16
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 16


def test_extra_space_in_view_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the  view<result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 15
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 16


def test_view_requires_local_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view</result> {\n"
            + "        it is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 21
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 27


def test_view_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 28
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 28


def test_view_requires_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result> {\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_view_requires_direction_statement_instead_of_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result> {\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 45


def test_view_extra_space_in_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result> {\n"
            + "        it  is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 11
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 12


def test_view_disallows_quality_assignment_block(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidLogicalOperationViewDefinitionBlock
    ) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<result> {\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 45


def test_view_control_character_in_statement_after_direction_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is read.\n"
            + "        it is \x00written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\x00"
    assert error.value.location.line == 4
    assert error.value.location.column == 15
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 15


def test_view_extra_space_in_statement_after_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is read.\n"
            + "        it  is written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 11
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 12


def test_view_disallows_written_before_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is written.\n"
            + "        it is read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_view_disallows_repeated_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is read.\n"
            + "        it is read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_view_requires_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is written.\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 24


def test_requires_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<a> {\n"
            + "        it is written.\n"
            + "    }\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 62


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
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
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 70
