# pyright: reportUnusedCallResult=false
"""Operation Execution Statement parser tests within Action Statements Blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


_ACTION_PREFIX = (
    "define the potential action<mv:define-lang.org:parser:/run> {\n"
    + "    define the position<p>.\n"
    + "    it happens when {\n"
    + "        the position<p> has a particle.\n"
    + "    } and it does {\n"
)

_ACTION_SUFFIX = "    }\n}\n"


def _action_statements(program: ast.Program) -> tuple[ast.ActionStatement, ...]:
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    return definition.action_statements.statements


def test_operation_execution_without_arguments(native_parse: NativeParse):
    [statement] = _action_statements(
        native_parse(
            _ACTION_PREFIX + "        execute the operation</add>.\n" + _ACTION_SUFFIX
        )
    )
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_type == name_types.NameType.OPERATION
    assert statement.operation.name_content.path.name == "/add"
    assert statement.arguments == ()
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=36
    )


def test_operation_execution_with_arguments(native_parse: NativeParse):
    [statement] = _action_statements(
        native_parse(
            _ACTION_PREFIX
            + "        execute the operation<mv:define-lang.org:parser:/add> {\n"
            + "            with view<a> looking at position<p>.\n"
            + "            with view<b> looking at position</global>::position<child>.\n"
            + '            with view<c> looking at literal</number>"12".\n'
            + "        }\n"
            + _ACTION_SUFFIX
        )
    )
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_content.path.name == "/add"
    [position_argument, chain_argument, literal_argument] = statement.arguments
    assert position_argument.view.name_content.name == "a"
    looking_at_position = position_argument.looking_at
    assert isinstance(looking_at_position, ast.PositionReference)
    [position] = looking_at_position.typed_names
    assert isinstance(position, ast.LocalTypedNameReference)
    assert position.name_content.name == "p"
    assert position_argument.location == ast.SourceLocation(
        line=7, column=13, end_line=7, end_column=48
    )
    assert chain_argument.view.name_content.name == "b"
    looking_at_chain = chain_argument.looking_at
    assert isinstance(looking_at_chain, ast.PositionReference)
    [parent, child] = looking_at_chain.typed_names
    assert isinstance(parent, ast.GlobalTypedNameReference)
    assert parent.name_content.path.name == "/global"
    assert isinstance(child, ast.LocalTypedNameReference)
    assert child.name_content.name == "child"
    assert chain_argument.location == ast.SourceLocation(
        line=8, column=13, end_line=8, end_column=71
    )
    assert literal_argument.view.name_content.name == "c"
    looking_at_literal = literal_argument.looking_at
    assert isinstance(looking_at_literal, ast.Literal)
    assert looking_at_literal.content == "12"
    assert literal_argument.location == ast.SourceLocation(
        line=9, column=13, end_line=9, end_column=57
    )
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=10, end_column=9
    )


def test_operation_execution_among_action_statements(native_parse: NativeParse):
    [local_position, create, add, clear, destroy] = _action_statements(
        native_parse(
            _ACTION_PREFIX
            + "        define the position<q>.\n"
            + "\n"
            + "        create a particle in position<q>.\n"
            + "        execute the operation</add> { # comment\n"
            + "\n"
            + "            with view<a> looking at position<q>. # comment\n"
            + "\n"
            + "        } # comment\n"
            + "\n"
            + "        execute the operation</clear>. # comment\n"
            + "        destroy the particle in position<q>.\n"
            + _ACTION_SUFFIX
        )
    )
    assert isinstance(local_position, ast.LocalPositionDefinition)
    assert isinstance(create, ast.CreateParticleStatement)
    assert isinstance(add, ast.OperationExecutionStatement)
    assert add.operation.name_content.path.name == "/add"
    [argument] = add.arguments
    assert argument.location == ast.SourceLocation(
        line=11, column=13, end_line=11, end_column=48
    )
    assert add.location == ast.SourceLocation(
        line=9, column=9, end_line=13, end_column=9
    )
    assert isinstance(clear, ast.OperationExecutionStatement)
    assert clear.operation.name_content.path.name == "/clear"
    assert clear.location == ast.SourceLocation(
        line=15, column=9, end_line=15, end_column=38
    )
    assert isinstance(destroy, ast.DestroyParticleStatement)


def test_disallows_encoding_operation_execution(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        native_parse(
            _ACTION_PREFIX
            + "        execute the encoding operation.\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 21
    assert error.value.location.end_line == 6
    assert error.value.location.end_column == 28


def test_operation_execution_requires_terminator_or_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        native_parse(
            _ACTION_PREFIX + "        execute the operation</add>\n" + _ACTION_SUFFIX
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 36
    assert error.value.location.end_line == 6
    assert error.value.location.end_column == 36


def test_operation_name_type_cannot_be_position(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        native_parse(
            _ACTION_PREFIX + "        execute the position</add>.\n" + _ACTION_SUFFIX
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 21
    assert error.value.location.end_line == 6
    assert error.value.location.end_column == 28


def test_operation_missing_space_after_execute_the(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as error:
        native_parse(
            _ACTION_PREFIX + "        execute theoperation</add>.\n" + _ACTION_SUFFIX
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 20
    assert error.value.location.end_line == 6
    assert error.value.location.end_column == 28


def test_arguments_block_requires_argument(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingOperationArgumentsContent) as error:
        native_parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 9
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 9


def test_arguments_block_disallows_action_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        native_parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            create a particle in position<p>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 13
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 45


def test_arguments_block_disallows_action_statement_after_first_argument(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidOperationArgumentsBlock) as error:
        native_parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            with view<a> looking at position<p>.\n"
            + "            create a particle in position<p>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 8
    assert error.value.location.column == 13
    assert error.value.location.end_line == 8
    assert error.value.location.end_column == 45


def test_argument_cannot_look_at_value(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedValueSource) as error:
        native_parse(
            _ACTION_PREFIX
            + "        execute the operation</add> {\n"
            + "            with view<a> looking at value<b>.\n"
            + "        }\n"
            + _ACTION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 37
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 41
