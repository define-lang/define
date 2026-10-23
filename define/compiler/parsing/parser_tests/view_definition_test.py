# pyright: reportUnusedCallResult=false
"""View definition parser tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


_OPERATION_PREFIX = "define the operation<mv:define-lang.org:parser:/add> {\n"

_OPERATION_SUFFIX = (
    "    it does {\n" + "        execute the encoding operation.\n" + "    }\n" + "}\n"
)


def _only_view(program: ast.Program) -> ast.ViewDefinition:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    [view] = definition.views
    return view


def test_value_constraint(native_parse: NativeParse):
    view = _only_view(
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    )
    [requirement] = view.constraints.requirements
    assert requirement.typed_global_name.name_type == name_types.NameType.VALUE
    assert requirement.typed_global_name.name_content.path.name == "/number"
    assert requirement.location == ast.SourceLocation(
        line=5, column=13, end_line=5, end_column=38
    )


def test_value_and_encoding_constraints(native_parse: NativeParse):
    view = _only_view(
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value<mv:define-lang.org:parser:/number>.\n"
            + "            it has the encoding</decimal>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    )
    [value, encoding] = view.constraints.requirements
    assert value.typed_global_name.name_type == name_types.NameType.VALUE
    assert value.typed_global_name.name_content.path.name == "/number"
    assert value.location == ast.SourceLocation(
        line=5, column=13, end_line=5, end_column=64
    )
    assert encoding.typed_global_name.name_type == name_types.NameType.ENCODING
    assert encoding.typed_global_name.name_content.path.name == "/decimal"
    assert encoding.location == ast.SourceLocation(
        line=6, column=13, end_line=6, end_column=42
    )


def test_requires_local_name(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view</left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 21
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 25


def test_requires_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        native_parse(
            _OPERATION_PREFIX + "    define the view<left>.\n" + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 26
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 26


def test_read_and_written(native_parse: NativeParse):
    view = _only_view(
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert view.is_input
    assert view.is_output


def test_written_only(native_parse: NativeParse):
    view = _only_view(
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert not view.is_input
    assert view.is_output


def test_blank_lines_between_direction_statements(native_parse: NativeParse):
    view = _only_view(
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "\n"
            + "        it is written.\n"
            + "\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    )
    assert view.is_input
    assert view.is_output
    assert view.constraints.location == ast.SourceLocation(
        line=7, column=9, end_line=9, end_column=9
    )


def test_requires_direction_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 45


def test_requires_direction_statement_in_empty_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_disallows_written_before_read(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is written.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_disallows_repeated_read(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 19


def test_disallows_repeated_written(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 22


def test_disallows_repeated_written_without_read(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is written.\n"
            + "        it is written.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 22


def test_disallows_read_after_read_and_written(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 19


def test_disallows_direction_statement_after_constraint_block(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "        it is written.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 9
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 22


def test_requires_constraint_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewConstraintBlock) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 5
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 5


def test_requires_constraint_block_after_both_directions(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewConstraintBlock) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it is written.\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 34


def test_disallows_direction_statement_in_position_definition(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as error:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the position<p> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 19


def test_requires_constraint(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingPositionConstraintContent) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 9
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 9


def test_disallows_literal_constraint(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the literal</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 24
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 30


def test_disallows_quality_implication(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        native_parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "        it also assigns the position</a>.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 41


def test_disallows_direction_statement_after_potential_position_constraint_block(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/p> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + "    it is read.\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 5
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 15


def test_disallows_direction_statement_after_local_position_constraint_block(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the position<p> {\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "        it is written.\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 6
    assert error.value.location.column == 9
    assert error.value.location.end_line == 6
    assert error.value.location.end_column == 22


def test_disallows_global_context(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        native_parse(
            "define the view<left> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 1
    assert error.value.location.column == 1
    assert error.value.location.end_line == 1
    assert error.value.location.end_column == 23


def test_disallows_action_context(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidActionDefinitionsBlock) as error:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/test> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        create a particle in position<p>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 2
    assert error.value.location.column == 5
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 27


def test_read_requires_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        native_parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 19
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 19


def test_written_requires_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as error:
        native_parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is written\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 22
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 22


def test_requires_direction_statement_instead_of_other_text(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        native_parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is red.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 9
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 18


def test_disallows_quality_implication_after_direction_statements(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.MissingViewConstraintBlock) as error:
        native_parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it also assigns the position</a>.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 9
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 41


def test_disallows_statement_after_constraint_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        native_parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "        it has the value</number>.\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 9
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 34
