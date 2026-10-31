# pyright: reportUnusedCallResult=false
"""Value quality definition parser tests."""

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


def _only_value(program: ast.Program) -> ast.ValueDefinition:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueDefinition)
    return definition


def test_value_definition(parse: Parse):
    definition = _only_value(
        parse(
            "define the potential value<mv:define-lang.org:parser:/number/natural> {\n"
            + "    it supports the logical_operation<mv:define-lang.org:parser:/add> {\n"
            + "        it may be read.\n"
            + "        it may be written.\n"
            + "    }\n"
            + "    it supports the logical_operation</negate> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    )
    assert definition.typed_name.name_type == name_types.NameType.VALUE
    assert definition.typed_name.name_content.path.name == "/number/natural"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=69
    )
    [add, negate] = definition.logical_operation_support_statements
    assert add.logical_operation.name_type == name_types.NameType.LOGICAL_OPERATION
    assert add.logical_operation.name_content.path.name == "/add"
    assert add.logical_operation.location == ast.SourceLocation(
        line=2, column=21, end_line=2, end_column=69
    )
    assert add.may_be_read
    assert add.may_be_written
    assert add.location == ast.SourceLocation(
        line=2, column=5, end_line=5, end_column=5
    )
    assert negate.logical_operation.name_type == (name_types.NameType.LOGICAL_OPERATION)
    assert negate.logical_operation.name_content.fqun is None
    assert negate.logical_operation.name_content.path.name == "/negate"
    assert negate.logical_operation.location == ast.SourceLocation(
        line=6, column=21, end_line=6, end_column=46
    )
    assert negate.may_be_read
    assert not negate.may_be_written
    assert negate.location == ast.SourceLocation(
        line=6, column=5, end_line=8, end_column=5
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=9, end_column=1
    )


def test_written_only(parse: Parse):
    definition = _only_value(
        parse(
            "define the potential value<mv:define-lang.org:parser:/boolean> {\n"
            + "    it supports the logical_operation</less_than> {\n"
            + "        it may be written.\n"
            + "    }\n"
            + "}\n"
        )
    )
    [statement] = definition.logical_operation_support_statements
    assert not statement.may_be_read
    assert statement.may_be_written
    assert statement.location == ast.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )


def test_comments_and_blank_lines(parse: Parse):
    definition = _only_value(
        parse(
            "define the potential value<mv:define-lang.org:parser:/number> { # comment\n"
            + "\n"
            + "    # comment\n"
            + "    it supports the logical_operation</add> { # comment\n"
            + "\n"
            + "        it may be read. # comment\n"
            + "\n"
            + "        it may be written. # comment\n"
            + "\n"
            + "    } # comment\n"
            + "\n"
            + "    it supports the logical_operation</negate> { # comment\n"
            + "        it may be written. # comment\n"
            + "    } # comment\n"
            + "\n"
            + "} # comment\n"
        )
    )
    [add, negate] = definition.logical_operation_support_statements
    assert add.may_be_read
    assert add.may_be_written
    assert add.location == ast.SourceLocation(
        line=4, column=5, end_line=10, end_column=5
    )
    assert not negate.may_be_read
    assert negate.may_be_written
    assert negate.location == ast.SourceLocation(
        line=12, column=5, end_line=14, end_column=5
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=16, end_column=1
    )


def test_read_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential value<mv:define-lang.org:parser:/number> {\n"
        + "    it supports the logical_operation</add> {\n"
        + "        it may be read\n"
        + "        it may be written.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=23, end_line=3, end_column=23)
        )
    ]
    assert result.program is not None
    [statement] = _only_value(result.program).logical_operation_support_statements
    assert statement.may_be_read
    assert statement.may_be_written


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the potential value<rational> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 28
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 35


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the potential value<standard:/number/natural>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 53
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 53


def test_requires_logical_operation_support_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLogicalOperationSupportStatement
    ) as error:
        parse("define the potential value<standard:/number/natural> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 1


def test_requires_logical_operation_support_statement_before_end_of_source(
    parse: Parse,
):
    with pytest.raises(
        parser_exceptions.MissingLogicalOperationSupportStatement
    ) as error:
        parse("define the potential value<standard:/number/natural> {\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 55
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 55


def test_disallows_other_statements(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueDefinitionBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it has the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 34


def test_disallows_other_statement_after_logical_operation_support_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidValueDefinitionBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "    it has the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 34


def test_control_character_in_logical_operation_support_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports \x00the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\x00"
    assert error.value.location.line == 2
    assert error.value.location.column == 17
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 17


def test_extra_space_in_logical_operation_support_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it  supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 7
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 8


def test_requires_logical_operation_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueDefinitionBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 21
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 29


def test_requires_logical_operation_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidValueDefinitionBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 20
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 20


def test_logical_operation_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation<add> {\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 39
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 41


def test_logical_operation_support_statement_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add>.\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 44
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 44


def test_logical_operation_support_block_requires_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLogicalOperationSupportBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_logical_operation_support_block_requires_statement_before_end_of_source(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidLogicalOperationSupportBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 46
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 46


def test_logical_operation_support_block_disallows_view_direction_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidLogicalOperationSupportBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it is read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 19


def test_logical_operation_support_block_disallows_written_before_read(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidLogicalOperationSupportBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be written.\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 23


def test_logical_operation_support_block_disallows_repeated_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidLogicalOperationSupportBlock) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "        it may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 23


def test_extra_space_in_logical_operation_support_block(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it  may be read.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 11
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 12


def test_control_character_in_logical_operation_support_block(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "        it may be \x00written.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\x00"
    assert error.value.location.line == 4
    assert error.value.location.column == 19
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_logical_operation_support_block_requires_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 45


def test_requires_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the potential value<standard:/number/natural> {\n"
            + "    it supports the logical_operation</add> {\n"
            + "        it may be read.\n"
            + "    }\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 54
