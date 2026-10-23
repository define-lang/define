# pyright: reportUnusedCallResult=false
"""Value operation definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_operation_definition(parse: Parse):
    program = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    assert definition.typed_name.name_type == name_types.NameType.OPERATION
    assert definition.typed_name.name_content.path.name == "/add"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=12, end_line=1, end_column=52
    )
    assert definition.views == ()
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.EncodingOperationExecutionStatement)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )


def test_operation_definition_with_views(parse: Parse):
    program = parse(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the view<right> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    [left, right] = definition.views
    assert left.typed_name.name_type == name_types.NameType.VIEW
    assert left.typed_name.name_content.name == "left"
    assert left.typed_name.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=25
    )
    assert left.location == ast.SourceLocation(
        line=2, column=5, end_line=7, end_column=5
    )
    assert right.typed_name.name_type == name_types.NameType.VIEW
    assert right.typed_name.name_content.name == "right"
    assert right.typed_name.location == ast.SourceLocation(
        line=8, column=16, end_line=8, end_column=26
    )
    assert right.location == ast.SourceLocation(
        line=8, column=5, end_line=13, end_column=5
    )


def test_comments_and_blank_lines(parse: Parse):
    program = parse(
        "define the operation<mv:define-lang.org:parser:/add> { # comment\n"
        + "\n"
        + "    # comment\n"
        + "    define the view<left> { # comment\n"
        + "\n"
        + "        it is read. # comment\n"
        + "\n"
        + "        it may only contain particles where { # comment\n"
        + "\n"
        + "            it has the value</number>. # comment\n"
        + "\n"
        + "        } # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "    it does { # comment\n"
        + "\n"
        + "        execute the encoding operation. # comment\n"
        + "\n"
        + "    } # comment\n"
        + "\n"
        + "} # comment\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    [view] = definition.views
    assert view.typed_name.name_content.name == "left"
    assert view.location == ast.SourceLocation(
        line=4, column=5, end_line=14, end_column=5
    )
    [statement] = definition.operation_statements
    assert isinstance(statement, ast.EncodingOperationExecutionStatement)
    assert statement.location == ast.SourceLocation(
        line=18, column=9, end_line=18, end_column=39
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=22, end_column=1
    )


def test_between_other_definitions(parse: Parse):
    program = parse(
        "define the potential value<mv:define-lang.org:parser:/number>.\n"
        + "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
        + "define the encoding<mv:define-lang.org:parser:/decimal>.\n"
    )
    [value, operation, encoding] = program.definitions
    assert isinstance(value, ast.ValueDefinition)
    assert isinstance(operation, ast.ValueOperationDefinition)
    assert operation.typed_name.name_content.path.name == "/add"
    assert operation.location == ast.SourceLocation(
        line=2, column=1, end_line=6, end_column=1
    )
    assert isinstance(encoding, ast.EncodingDefinition)


def test_requires_global_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as error:
        parse(
            "define the operation<add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 22
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 24


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse("define the operation<mv:define-lang.org:parser:/add>.\n")
    assert error.value.location.line == 1
    assert error.value.location.column == 53
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 53


def test_requires_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationStatementsBlock) as error:
        parse("define the operation<mv:define-lang.org:parser:/add> {\n}\n")
    assert error.value.location.line == 2
    assert error.value.location.column == 1
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 1


def test_requires_operation_statements_block_after_views(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOperationStatementsBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 8
    assert error.value.location.column == 1
    assert error.value.location.end_line == 8
    assert error.value.location.end_column == 1


def test_disallows_local_position_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the position<p>.\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 27


def test_disallows_view_after_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 27


def test_disallows_second_operation_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
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


def test_missing_close_brace_at_eof(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 54


def test_operation_statements_block_extra_whitespace(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does  {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 12
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 13


def test_disallows_local_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        define the operation<mv:define-lang.org:parser:/add> {\n"
            + "            it does {\n"
            + "                execute the encoding operation.\n"
            + "            }\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidOperationDefinitionBlock) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it also assigns the position</a>.\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 37
