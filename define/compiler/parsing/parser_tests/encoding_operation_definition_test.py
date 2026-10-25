# pyright: reportUnusedCallResult=false
"""Encoding Operation definition parser tests."""

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


_ENCODING_OPERATION_PREFIX = (
    "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
    + "    it does {\n"
)

_ENCODING_OPERATION_SUFFIX = "    }\n}\n"


def _only_encoding_operation(program: ast.Program) -> ast.EncodingOperationDefinition:
    [definition] = program.definitions
    assert isinstance(definition, ast.EncodingOperationDefinition)
    return definition


def test_encoding_operation_definition(parse: Parse):
    definition = _only_encoding_operation(
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    )
    assert definition.typed_name.name_type == name_types.NameType.ENCODING_OPERATION
    assert definition.typed_name.name_content.path.name == "/add"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=12, end_line=1, end_column=61
    )
    assert definition.views == ()
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.ComputerOperationExecutionStatement)
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=39
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )


def test_encoding_operation_definition_with_views(parse: Parse):
    definition = _only_encoding_operation(
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the encoding</decimal>.\n"
            + "        }\n"
            + "    }\n"
            + "    define the view<right> {\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the encoding</decimal>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    )
    [left, right] = definition.views
    assert left.typed_name.name_content.name == "left"
    assert left.location == ast.SourceLocation(
        line=2, column=5, end_line=7, end_column=5
    )
    assert right.typed_name.name_content.name == "right"
    assert right.location == ast.SourceLocation(
        line=8, column=5, end_line=13, end_column=5
    )


def test_encoding_operation_execution_without_arguments(parse: Parse):
    definition = _only_encoding_operation(
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    )
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_type == name_types.NameType.ENCODING_OPERATION
    assert statement.operation.name_content.fqun is None
    assert statement.operation.name_content.path.name == "/other"
    assert statement.operation.location == ast.SourceLocation(
        line=3, column=21, end_line=3, end_column=46
    )
    assert statement.arguments == ()
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=47
    )


def test_encoding_operation_execution_with_arguments(parse: Parse):
    definition = _only_encoding_operation(
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation<mv:define-lang.org:parser:/other> {\n"
            + "            with view<a> looking at view<left>.\n"
            + '            with view<b> looking at literal</number>"12".\n'
            + "        }\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    )
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.OperationExecutionStatement)
    assert statement.operation.name_type == name_types.NameType.ENCODING_OPERATION
    fqun = statement.operation.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert statement.operation.name_content.path.name == "/other"
    [view_argument, literal_argument] = statement.arguments
    assert view_argument.view.name_content.name == "a"
    looking_at_view = view_argument.looking_at
    assert isinstance(looking_at_view, ast.LocalTypedNameReference)
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


def test_encoding_operation_argument_looking_at_position_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        _ENCODING_OPERATION_PREFIX
        + "        execute the encoding_operation</other> {\n"
        + "            with view<a> looking at position<p>.\n"
        + "        }\n"
        + _ENCODING_OPERATION_SUFFIX
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.OperationArgumentPositionDiagnostic(
            location=ast.SourceLocation(line=4, column=37, end_line=4, end_column=47),
            position_name="position<p>",
        )
    ]
    assert result.program is not None
    definition = _only_encoding_operation(result.program)
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.OperationExecutionStatement)
    [argument] = statement.arguments
    assert isinstance(argument.looking_at, ast.PositionReference)
    assert argument.location == ast.SourceLocation(
        line=4, column=13, end_line=4, end_column=48
    )


def test_multiple_statements_comments_and_blank_lines(parse: Parse):
    definition = _only_encoding_operation(
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> { # comment\n"
            + "\n"
            + "    # comment\n"
            + "    define the view<left> { # comment\n"
            + "\n"
            + "        it is read. # comment\n"
            + "\n"
            + "        it may only contain particles where { # comment\n"
            + "\n"
            + "            it has the encoding</decimal>. # comment\n"
            + "\n"
            + "        } # comment\n"
            + "\n"
            + "    } # comment\n"
            + "\n"
            + "    it does { # comment\n"
            + "\n"
            + "        execute the encoding_operation</first>. # comment\n"
            + "\n"
            + "        execute the encoding_operation</second> { # comment\n"
            + "\n"
            + "            with view<a> looking at view<left>. # comment\n"
            + "\n"
            + "        } # comment\n"
            + "\n"
            + "        execute the computer operation. # comment\n"
            + "\n"
            + "    } # comment\n"
            + "\n"
            + "} # comment\n"
        )
    )
    [view] = definition.views
    assert view.location == ast.SourceLocation(
        line=4, column=5, end_line=14, end_column=5
    )
    [first, second, third] = definition.operation_statements
    assert isinstance(first, ast.OperationExecutionStatement)
    assert first.operation.name_content.path.name == "/first"
    assert first.location == ast.SourceLocation(
        line=18, column=9, end_line=18, end_column=47
    )
    assert isinstance(second, ast.OperationExecutionStatement)
    assert second.operation.name_content.path.name == "/second"
    [argument] = second.arguments
    assert argument.location == ast.SourceLocation(
        line=22, column=13, end_line=22, end_column=47
    )
    assert second.location == ast.SourceLocation(
        line=20, column=9, end_line=24, end_column=9
    )
    assert isinstance(third, ast.ComputerOperationExecutionStatement)
    assert third.location == ast.SourceLocation(
        line=26, column=9, end_line=26, end_column=39
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=30, end_column=1
    )


def test_between_other_definitions(parse: Parse):
    program = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding_operation<mv:define-lang.org:parser:/add_decimal> {\n"
        + "    it does {\n"
        + "        execute the computer operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding<mv:define-lang.org:parser:/decimal>.\n"
    )
    [operation, encoding_operation, encoding] = program.definitions
    assert isinstance(operation, ast.ValueOperationDefinition)
    assert isinstance(encoding_operation, ast.EncodingOperationDefinition)
    assert encoding_operation.typed_name.name_content.path.name == "/add_decimal"
    assert encoding_operation.location == ast.SourceLocation(
        line=6, column=1, end_line=10, end_column=1
    )
    assert isinstance(encoding, ast.EncodingDefinition)


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the encoding_operation<add> {\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 31
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 33


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the encoding_operation<mv:define-lang.org:parser:/add>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 62
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 62


def test_requires_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationStatementsBlock) as error:
        parse("define the encoding_operation<mv:define-lang.org:parser:/add> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 1


def test_disallows_local_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the position<p>.\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 27


def test_requires_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingEncodingOperationStatementsContent
    ) as error:
        parse(_ENCODING_OPERATION_PREFIX + _ENCODING_OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_disallows_action_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        create a particle in position<p>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 41


def test_disallows_action_statement_after_first_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the computer operation.\n"
            + "        create a particle in position<p>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 41


def test_disallows_encoding_operation_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding operation.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_disallows_value_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the operation</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 29


def test_encoding_operation_name_type_cannot_be_position(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedEncodingOperation) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the position</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_encoding_operation_extra_space_after_execute_the(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the  encoding_operation</other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 20
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 21


def test_computer_operation_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        _ENCODING_OPERATION_PREFIX
        + "        execute the computer operation\n"
        + _ENCODING_OPERATION_SUFFIX
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=39, end_line=3, end_column=39)
        )
    ]
    assert result.program is not None
    definition = _only_encoding_operation(result.program)
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.ComputerOperationExecutionStatement)
    assert statement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=38
    )


def test_encoding_operation_execution_requires_terminator_or_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation</other>\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 47
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 47


def test_encoding_operation_execution_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation<other>.\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 40
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 44


def test_arguments_block_requires_argument(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationArgumentsContent) as error:
        parse(
            _ENCODING_OPERATION_PREFIX
            + "        execute the encoding_operation</other> {\n"
            + "        }\n"
            + _ENCODING_OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 9


def test_value_operation_disallows_computer_operation(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the computer operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_value_operation_disallows_encoding_operation_execution(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding_operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 21
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 38


def test_action_disallows_encoding_operation_execution(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedOperation) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        execute the encoding_operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 21
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 38


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "            it does {\n"
            + "                execute the computer operation.\n"
            + "            }\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 71


def test_computer_operation_is_not_a_global_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        parse("execute the computer operation.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 31
