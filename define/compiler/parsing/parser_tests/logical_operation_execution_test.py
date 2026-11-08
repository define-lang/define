# pyright: reportUnusedCallResult=false
"""Logical Operation Execution Statement parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


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


def test_argument_cannot_look_at_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedView) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at position<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 44


def test_requires_arguments_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 44
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 44


def test_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationArgumentsContent) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 9


def test_requires_open_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation /and {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 38
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 38


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation<and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 39
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 41


def test_extra_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the  logical_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 21


def test_missing_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute thelogical_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 36


def test_invisible_character_in_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logi\u200bcal_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 3
    assert error.value.location.column == 25
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 25


def test_value_operation_name_type_cannot_be_view(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperationOrLogicalOperation) as error:
        parse(_OPERATION_PREFIX + "        execute the view<v>.\n" + _OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 24


def test_logical_operation_disallows_literal(parse: Parse):
    with pytest.raises(parser_exceptions.LiteralInLogicalOperationExecution) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + '            with view<a> looking at literal</number>"12".\n'
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 43


def test_logical_operation_word_starting_with_literal(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedView) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at literally<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 45


def test_logical_operation_looks_at_non_word(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedView) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + '            with view<a> looking at "12".\n'
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 40


def test_argument_requires_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentSyntax) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 26
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 29


def test_argument_source_requires_local_view_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view</p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 42
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 43


def test_argument_followed_by_text(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<p> extra.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 44
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 44


def test_carriage_return_in_comment_before_first_argument(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            # note\r\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.escaped_char == "\\r"
    assert error.value.location.line == 4
    assert error.value.location.column == 19
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_carriage_return_in_comment_after_argument(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "            # note\r\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.escaped_char == "\\r"
    assert error.value.location.line == 5
    assert error.value.location.column == 19
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 19


def test_encoding_operation_disallows_logical_operation(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<p>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 37


def test_action_disallows_logical_operation(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
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
    assert error.value.location.line == 5
    assert error.value.location.column == 21
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 37
