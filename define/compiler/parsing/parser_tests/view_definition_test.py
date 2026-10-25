# pyright: reportUnusedCallResult=false
"""View definition parser tests."""

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


_OPERATION_PREFIX = "define the operation<mv:define-lang.org:parser:/add> {\n"

_OPERATION_SUFFIX = (
    "    it does {\n" + "        execute the encoding operation.\n" + "    }\n" + "}\n"
)


def _only_view(program: ast.Program) -> ast.ViewDefinition:
    [definition] = program.definitions
    assert isinstance(definition, ast.ValueOperationDefinition)
    [view] = definition.views
    return view


def test_value_quality(parse: Parse):
    view = _only_view(
        parse(
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
    [quality_assignment] = view.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_type == name_types.NameType.VALUE
    assert quality_assignment.typed_global_name.name_content.path.name == "/number"
    assert quality_assignment.location == ast.SourceLocation(
        line=5, column=13, end_line=5, end_column=38
    )


def test_value_and_encoding_quality_assignments(parse: Parse):
    view = _only_view(
        parse(
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
    [value, encoding] = view.quality_assignment_block.statements
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


def test_requires_local_name(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as error:
        parse(
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


def test_requires_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as error:
        parse(_OPERATION_PREFIX + "    define the view<left>.\n" + _OPERATION_SUFFIX)
    assert error.value.location.line == 2
    assert error.value.location.column == 26
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 26


def test_read_and_written(parse: Parse):
    view = _only_view(
        parse(
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


def test_written_only(parse: Parse):
    view = _only_view(
        parse(
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


def test_blank_lines_between_direction_statements(parse: Parse):
    view = _only_view(
        parse(
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
    assert view.quality_assignment_block.location == ast.SourceLocation(
        line=7, column=9, end_line=9, end_column=9
    )


def test_requires_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
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


def test_requires_direction_statement_in_empty_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
            _OPERATION_PREFIX
            + "    define the view<left> {\n"
            + "    }\n"
            + _OPERATION_SUFFIX
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 5
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 5


def test_disallows_written_before_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_disallows_repeated_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_disallows_repeated_written(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_disallows_repeated_written_without_read(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_disallows_read_after_read_and_written(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_disallows_direction_statement_after_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidViewDirectionStatementOrder) as error:
        parse(
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


def test_requires_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewQualityAssignmentBlock) as error:
        parse(
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


def test_requires_quality_assignment_block_after_both_directions(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewQualityAssignmentBlock) as error:
        parse(
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
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as error:
        parse(
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


def test_requires_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.MissingQualityAssignmentBlockContent) as error:
        parse(
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


def test_disallows_literal_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedQualityAssignmentNameType) as error:
        parse(
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


def test_disallows_quality_implication(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
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


def test_disallows_direction_statement_after_potential_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
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


def test_disallows_direction_statement_after_local_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
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


def test_disallows_global_context(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as error:
        parse(
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


def test_disallows_action_context(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionDefinitionsBlock) as error:
        parse(
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


def test_read_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
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
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=19, end_line=3, end_column=19)
        )
    ]
    assert result.program is not None
    view = _only_view(result.program)
    assert view.is_input is True
    assert view.is_output is False


def test_written_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
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
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=22, end_line=3, end_column=22)
        )
    ]
    assert result.program is not None
    view = _only_view(result.program)
    assert view.is_input is False
    assert view.is_output is True


def test_requires_direction_statement_instead_of_other_text(parse: Parse):
    with pytest.raises(parser_exceptions.MissingViewDirectionStatement) as error:
        parse(
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
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingViewQualityAssignmentBlock) as error:
        parse(
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


def test_disallows_statement_after_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as error:
        parse(
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
