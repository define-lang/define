# pyright: reportUnusedCallResult=false
"""Logical Operation Execution Statement parser tests."""

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


_OPERATION_PREFIX = (
    "define the operation<mv:define-lang.org:parser:/add> {\n" + "    it does {\n"
)

_OPERATION_SUFFIX = "    }\n}\n"


def _operation_statements(
    program: ast.Program,
) -> tuple[ast.OperationStatement, ...]:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    return definition.operation_statements


def test_logical_operation_execution(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the logical_operation</and> {\n"
            + "            with view<a> looking at view<left>.\n"
            + '            with view<b> looking at literal</number>"12".\n'
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.LogicalOperationExecutionStatement)
    logical_operation = statement.logical_operation
    assert logical_operation.name_type == name_types.NameType.LOGICAL_OPERATION
    assert logical_operation.name_content.fqun is None
    assert logical_operation.name_content.path.name == "/and"
    assert logical_operation.location == ast.SourceLocation(
        line=3, column=21, end_line=3, end_column=43
    )
    [view_argument, literal_argument] = statement.arguments
    assert view_argument.view.name_type == name_types.NameType.VIEW
    assert view_argument.view.name_content.name == "a"
    looking_at_view = view_argument.looking_at
    assert isinstance(looking_at_view, ast.LocalTypedNameReference)
    assert looking_at_view.name_type == name_types.NameType.VIEW
    assert looking_at_view.name_content.name == "left"
    assert view_argument.location == ast.SourceLocation(
        line=4, column=13, end_line=4, end_column=47
    )
    assert literal_argument.view.name_content.name == "b"
    looking_at_literal = literal_argument.looking_at
    assert isinstance(looking_at_literal, ast.Literal)
    assert looking_at_literal.content == "12"
    assert literal_argument.location == ast.SourceLocation(
        line=5, column=13, end_line=5, end_column=57
    )
    assert statement.location == ast.SourceLocation(
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
    assert argument.location == ast.SourceLocation(
        line=6, column=13, end_line=6, end_column=44
    )
    assert second.location == ast.SourceLocation(
        line=4, column=9, end_line=7, end_column=9
    )
    assert isinstance(third, ast.EncodingOperationExecutionStatement)


def test_argument_looking_at_position_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        _OPERATION_PREFIX
        + "        execute the logical_operation</and> {\n"
        + "            with view<a> looking at position<p>.\n"
        + "        }\n"
        + _OPERATION_SUFFIX
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.OperationArgumentPositionDiagnostic(
            location=ast.SourceLocation(line=4, column=37, end_line=4, end_column=47),
            position_name="position<p>",
        )
    ]
    assert result.program is not None
    [statement] = _operation_statements(result.program)
    assert isinstance(statement, ast.LogicalOperationExecutionStatement)
    [argument] = statement.arguments
    assert isinstance(argument.looking_at, ast.PositionReference)


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
