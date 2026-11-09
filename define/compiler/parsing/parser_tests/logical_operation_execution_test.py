# pyright: reportUnusedCallResult=false
"""Logical Operation Execution Statement parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast, name_types
from define.compiler.errors import syntax_errors
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
    )


_OPERATION_PREFIX = (
    "define the operation<mv:define-lang.org:parser:/add> {\n" + "    it does {\n"
)

_OPERATION_SUFFIX = "    }\n}\n"


def _operation_statements(
    program: ast.Program,
) -> tuple[ast.OperationStatement, ...]:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    return definition.operation_statements.statements


def test_logical_operation_execution(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<left>.\n"
            + "            with view<b> looking at view<right>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.LogicalOperationExecutionStatement)
    logical_operation = statement.logical_operation
    assert logical_operation.name_type == name_types.NameType.LOGICAL_OPERATION
    assert logical_operation.name_content.fqun is None
    assert logical_operation.name_content.path.name == "/and"
    assert logical_operation.location == rendering.SourceLocation(
        line=3, column=21, end_line=3, end_column=43
    )
    [first_argument, second_argument] = statement.arguments
    assert first_argument.view.name_type == name_types.NameType.VIEW
    assert first_argument.view.name_content.name == "a"
    assert first_argument.looking_at.name_type == name_types.NameType.VIEW
    assert first_argument.looking_at.name_content.name == "left"
    assert first_argument.location == rendering.SourceLocation(
        line=4, column=13, end_line=4, end_column=47
    )
    assert second_argument.view.name_content.name == "b"
    assert second_argument.looking_at.name_content.name == "right"
    assert second_argument.location == rendering.SourceLocation(
        line=5, column=13, end_line=5, end_column=48
    )
    assert statement.location == rendering.SourceLocation(
        line=3, column=9, end_line=6, end_column=9
    )


def test_logical_operation_with_fqun(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation<mv:define-lang.org:parser:/and> {\n"
            + "            with view<a> looking at view<left>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.LogicalOperationExecutionStatement)
    name_content = statement.logical_operation.name_content
    assert name_content.fqun is not None
    assert name_content.fqun.canonical == "mv:define-lang.org:parser"
    assert name_content.path.name == "/and"


def test_among_other_operation_statements(parse: Parse):
    [first, second, third] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</first>.\n"
            + "        execute the logical_operation</and> { # comment\n"
            + "\n"
            + "            with view<a> looking at view<p>. # comment\n"
            + "        } # comment\n"
            + "        execute the encoding operation.\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(first, ast.OperationExecutionStatement)
    assert isinstance(second, ast.LogicalOperationExecutionStatement)
    assert second.logical_operation.name_content.path.name == "/and"
    [argument] = second.arguments
    assert argument.location == rendering.SourceLocation(
        line=6, column=13, end_line=6, end_column=44
    )
    assert second.location == rendering.SourceLocation(
        line=4, column=9, end_line=7, end_column=9
    )
    assert isinstance(third, ast.EncodingOperationExecutionStatement)


def test_argument_cannot_look_at_position(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at position<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 4
    assert error.location.column == 37
    assert error.location.end_line == 4
    assert error.location.end_column == 44


def test_requires_arguments_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and>.\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingOpenBrace)
    assert error.location.line == 3
    assert error.location.column == 44
    assert error.location.end_line == 3
    assert error.location.end_column == 44


def test_requires_argument(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingOperationArgumentsContent)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 9


def test_requires_open_angle_bracket(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation /and {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingOpenAngleBracket)
    assert error.location.line == 3
    assert error.location.column == 38
    assert error.location.end_line == 3
    assert error.location.end_column == 38


def test_requires_global_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation<and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 3
    assert error.location.column == 39
    assert error.location.end_line == 3
    assert error.location.end_column == 41


def test_extra_space_after_execute_the(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the  logical_operation</and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 3
    assert error.location.column == 20
    assert error.location.end_line == 3
    assert error.location.end_column == 21


def test_missing_space_after_execute_the(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute thelogical_operation</and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 3
    assert error.location.column == 20
    assert error.location.end_line == 3
    assert error.location.end_column == 36


def test_invisible_character_in_name_type(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logi\u200bcal_operation</and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvisibleCharacterError)
    assert error.char == "\u200b"
    assert error.location.line == 3
    assert error.location.column == 25
    assert error.location.end_line == 3
    assert error.location.end_column == 25


def test_value_operation_name_type_cannot_be_view(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX + "        execute the view<v>.\n" + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedOperationOrLogicalOperation)
    assert error.location.line == 3
    assert error.location.column == 21
    assert error.location.end_line == 3
    assert error.location.end_column == 24


def test_logical_operation_disallows_literal(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + '            with view<a> looking at literal</number>"12".\n'
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.LiteralInLogicalOperationExecution)
    assert error.location.line == 4
    assert error.location.column == 37
    assert error.location.end_line == 4
    assert error.location.end_column == 43


def test_logical_operation_word_starting_with_literal(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at literally<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 4
    assert error.location.column == 37
    assert error.location.end_line == 4
    assert error.location.end_column == 45


def test_logical_operation_looks_at_non_word(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + '            with view<a> looking at "12".\n'
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.ExpectedView)
    assert error.location.line == 4
    assert error.location.column == 37
    assert error.location.end_line == 4
    assert error.location.end_column == 40


def test_argument_requires_looking_at(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.InvalidOperationArgumentSyntax)
    assert error.location.line == 4
    assert error.location.column == 26
    assert error.location.end_line == 4
    assert error.location.end_column == 29


def test_argument_source_requires_local_view_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at view</p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.GlobalNameWhereLocalNameExpected)
    assert error.location.line == 4
    assert error.location.column == 42
    assert error.location.end_line == 4
    assert error.location.end_column == 43


def test_argument_followed_by_text(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at view<p> extra.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.MissingTerminator)
    assert error.location.line == 4
    assert error.location.column == 44
    assert error.location.end_line == 4
    assert error.location.end_column == 44


def test_carriage_return_in_comment_before_first_argument(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            # note\r\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.CarriageReturnError)
    assert error.escaped_char == "\\r"
    assert error.location.line == 4
    assert error.location.column == 19
    assert error.location.end_line == 4
    assert error.location.end_column == 19


def test_carriage_return_in_comment_after_argument(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "            # note\r\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert isinstance(error, syntax_errors.CarriageReturnError)
    assert error.escaped_char == "\\r"
    assert error.location.line == 5
    assert error.location.column == 19
    assert error.location.end_line == 5
    assert error.location.end_column == 19


def test_encoding_operation_disallows_logical_operation(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at view<p>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedEncodingOperation)
    assert error.location.line == 3
    assert error.location.column == 21
    assert error.location.end_line == 3
    assert error.location.end_column == 37


def test_action_disallows_logical_operation(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at position<p>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedOperation)
    assert error.location.line == 5
    assert error.location.column == 21
    assert error.location.end_line == 5
    assert error.location.end_column == 37
