# pyright: reportUnusedCallResult=false
"""Operation Statements Block parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

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
    return definition.operation_statements


def test_encoding_operation_execution(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the encoding operation.\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.EncodingOperationExecutionStatement)
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=39
    )


def test_operation_execution_without_arguments(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other>.\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_type == name_types.NameType.OPERATION
    assert statement.operation.name_content.fqun is None
    assert statement.operation.name_content.path.name == "/other"
    assert statement.operation.location == ast.SourceLocation(
        line=3, column=21, end_line=3, end_column=37
    )
    assert statement.arguments == ()
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=38
    )


def test_operation_execution_with_arguments(parse: Parse):
    [statement] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the operation<mv:define-lang.org:parser:/other> {\n"
            + "            with view<a> looking at view<left>.\n"
            + "            with view<b> looking at position<p>.\n"
            + "            with view<c> looking at position</global>::position<child>.\n"
            + '            with view<d> looking at literal</number>"12".\n'
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_content.path.name == "/other"
    [view_argument, position_argument, chain_argument, literal_argument] = (
        statement.arguments
    )
    assert view_argument.view.name_type == name_types.NameType.VIEW
    assert view_argument.view.name_content.name == "a"
    assert view_argument.view.location == ast.SourceLocation(
        line=4, column=18, end_line=4, end_column=24
    )
    looking_at_view = view_argument.looking_at
    assert isinstance(looking_at_view, ast.LocalTypedNameReference)
    assert looking_at_view.name_type == name_types.NameType.VIEW
    assert looking_at_view.name_content.name == "left"
    assert looking_at_view.location == ast.SourceLocation(
        line=4, column=37, end_line=4, end_column=46
    )
    assert view_argument.location == ast.SourceLocation(
        line=4, column=13, end_line=4, end_column=47
    )
    assert position_argument.view.name_content.name == "b"
    looking_at_position = position_argument.looking_at
    assert isinstance(looking_at_position, ast.PositionReference)
    [position] = looking_at_position.typed_names
    assert isinstance(position, ast.LocalTypedNameReference)
    assert position.name_content.name == "p"
    assert position_argument.location == ast.SourceLocation(
        line=5, column=13, end_line=5, end_column=48
    )
    assert chain_argument.view.name_content.name == "c"
    looking_at_chain = chain_argument.looking_at
    assert isinstance(looking_at_chain, ast.PositionReference)
    [parent, child] = looking_at_chain.typed_names
    assert isinstance(parent, ast.GlobalTypedNameReference)
    assert parent.name_content.path.name == "/global"
    assert isinstance(child, ast.LocalTypedNameReference)
    assert child.name_content.name == "child"
    assert looking_at_chain.location == ast.SourceLocation(
        line=6, column=37, end_line=6, end_column=70
    )
    assert chain_argument.location == ast.SourceLocation(
        line=6, column=13, end_line=6, end_column=71
    )
    assert literal_argument.view.name_content.name == "d"
    looking_at_literal = literal_argument.looking_at
    assert isinstance(looking_at_literal, ast.Literal)
    assert looking_at_literal.content == "12"
    assert looking_at_literal.location == ast.SourceLocation(
        line=7, column=37, end_line=7, end_column=56
    )
    assert literal_argument.location == ast.SourceLocation(
        line=7, column=13, end_line=7, end_column=57
    )
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=8, end_column=9
    )


def test_multiple_statements_comments_and_blank_lines(parse: Parse):
    [first, second, third] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "\n"
            + "        execute the operation</first>. # comment\n"
            + "\n"
            + "        execute the operation</second> { # comment\n"
            + "\n"
            + "            with view<a> looking at view<p>. # comment\n"
            + "\n"
            + "        } # comment\n"
            + "\n"
            + "        execute the encoding operation. # comment\n"
            + "\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(first, ast.OperationExecutionStatement)
    assert first.operation.name_content.path.name == "/first"
    assert first.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=38
    )
    assert isinstance(second, ast.OperationExecutionStatement)
    assert second.operation.name_content.path.name == "/second"
    [argument] = second.arguments
    assert argument.location == ast.SourceLocation(
        line=8, column=13, end_line=8, end_column=44
    )
    assert second.location == ast.SourceLocation(
        line=6, column=9, end_line=10, end_column=9
    )
    assert isinstance(third, ast.EncodingOperationExecutionStatement)
    assert third.location == ast.SourceLocation(
        line=12, column=9, end_line=12, end_column=39
    )


def test_requires_statement(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationStatementsContent) as error:
        parse(_OPERATION_PREFIX + _OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_disallows_action_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "        create a particle in position<p>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 41


def test_disallows_action_statement_after_first_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the encoding operation.\n"
            + "        create a particle in position<p>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 41


def test_encoding_operation_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the encoding operation\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 39
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 39


def test_operation_execution_requires_terminator_or_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other>\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 38
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 38


def test_operation_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation<other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 31
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 35


def test_operation_requires_open_angle_bracket(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation /other.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 30
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 30


def test_operation_name_type_cannot_be_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the position</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_operation_name_type_cannot_be_action(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the action</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 26


def test_arguments_block_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationArgumentsContent) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 9


def test_argument_requires_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<p>\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 44
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 44


def test_argument_requires_local_view_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view</a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 23
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 24


def test_argument_requires_view_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedView) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with position<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 18
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 25


def test_argument_requires_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentSyntax) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> position<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 26
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 33


def test_operation_missing_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute theoperation</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_operation_extra_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the  operation</other>.\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 21


def test_argument_missing_space_after_with(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            withview<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 17
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 20


def test_argument_extra_space_after_with(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with  view<a> looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 17
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 18


def test_argument_missing_space_before_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a>looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 25
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 31


def test_argument_extra_space_before_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a>  looking at view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 25
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 26


def test_argument_missing_space_after_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking atview<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 36
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 39


def test_argument_extra_space_after_looking_at(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at  view<p>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 36
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 37


def test_argument_view_cannot_be_chained(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<p>::position<q>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 44
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 44


def test_argument_cannot_look_at_value(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedValueSource) as error:
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at value<b>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 37
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 41


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationStatementsBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        it also assigns the position</a>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 41


def test_arguments_block_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            it also assigns the position</a>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 13
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 45


def test_argument_source_requires_local_view_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view</p>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 42
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 43
