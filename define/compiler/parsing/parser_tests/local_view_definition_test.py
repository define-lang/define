# pyright: reportUnusedCallResult=false
"""Local View Definition parser tests."""

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
    return definition.operation_statements.statements


def test_local_view_definition(parse: Parse):
    [view, execution] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<sum>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(view, ast.LocalViewDefinition)
    assert view.typed_name.name_type == name_types.NameType.VIEW
    assert view.typed_name.name_content.name == "sum"
    assert view.typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=28
    )
    [quality_assignment] = view.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_type == name_types.NameType.VALUE
    assert quality_assignment.typed_global_name.name_content.path.name == "/number"
    assert quality_assignment.location == ast.SourceLocation(
        line=5, column=17, end_line=5, end_column=42
    )
    assert view.quality_assignment_block.location == ast.SourceLocation(
        line=4, column=13, end_line=6, end_column=13
    )
    assert view.location == ast.SourceLocation(
        line=3, column=9, end_line=7, end_column=9
    )
    assert isinstance(execution, ast.OperationExecutionStatement)


def test_local_view_after_execution(parse: Parse):
    [execution, view] = _operation_statements(
        parse(
            _OPERATION_PREFIX
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<b>.\n"
            + "        }\n"
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "                it has the encoding</decimal>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert isinstance(execution, ast.OperationExecutionStatement)
    assert isinstance(view, ast.LocalViewDefinition)
    assert view.typed_name.name_content.name == "sum"
    [value, encoding] = view.quality_assignment_block.statements
    assert value.typed_global_name.name_type == name_types.NameType.VALUE
    assert encoding.typed_global_name.name_type == name_types.NameType.ENCODING
    assert view.location == ast.SourceLocation(
        line=6, column=9, end_line=11, end_column=9
    )


def test_requires_local_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view</sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 25
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 28


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(_OPERATION_PREFIX + "        define the view<sum>.\n" + _OPERATION_SUFFIX)
    assert error.value.location.line == 3
    assert error.value.location.column == 29
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 29


def test_requires_quality_assignment_block(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLocalViewQualityAssignmentBlock
    ) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 9


def test_requires_quality_assignment_block_at_end_of_source(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLocalViewQualityAssignmentBlock
    ) as error:
        parse(_OPERATION_PREFIX + "        define the view<sum> {\n")
    assert error.value.location.line == 3
    assert error.value.location.column == 31
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 31


def test_requires_quality_assignment_statement(parse: Parse):
    with pytest.raises(parser_exceptions.MissingQualityAssignmentBlockContent) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 13
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 13


def test_disallows_view_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.LocalViewDirectionStatement) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it is read.\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 13
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 23


def test_disallows_view_direction_statement_after_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.LocalViewDirectionStatement) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "            it is written.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 13
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 26


def test_disallows_statement_after_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 13
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 38


def test_requires_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 30


def test_disallows_other_statement(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingLocalViewQualityAssignmentBlock
    ) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 13
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 38


def test_misspaced_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only  contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 24
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 25


def test_invisible_character_in_quality_assignment_block_start(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            it may only\u200b contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 4
    assert error.value.location.column == 24
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 24


def test_carriage_return_in_comment_before_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the view<sum> {\n"
            + "            # note\r\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.char == "\r"
    assert error.value.location.line == 4
    assert error.value.location.column == 19
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_misspaced_local_view_definition(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as error:
        parse(
            _OPERATION_PREFIX
            + "        define the  view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the value</number>.\n"
            + "            }\n"
            + "        }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 19
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 20


def test_encoding_operation_disallows_local_view(parse: Parse):
    with pytest.raises(
        parser_exceptions.InvalidEncodingOperationStatementsBlock
    ) as error:
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        define the view<sum> {\n"
            + "            it may only contain particles where {\n"
            + "                it has the encoding</decimal>.\n"
            + "            }\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 30
