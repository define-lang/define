# pyright: reportUnusedCallResult=false
"""Destructor condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


def test_destructor_with_no_interface_positions(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is being destroyed.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.DestructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=41
    )
    assert definition.interface_positions == ()


def test_destructor_with_comments(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        this particle is being destroyed.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.DestructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=41
    )


def test_destructor_with_blank_lines(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "\n"
        + "        this particle is being destroyed.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.DestructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=41
    )


def test_destructor_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is being destroyed\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=41, end_line=3, end_column=41)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.DestructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=40
    )


def test_destructor_followed_by_extra_content(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed now.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 41
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 41


def test_trigger_condition_and_destructor_in_one_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "        this particle is being destroyed.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 41


def test_destructor_as_action_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        this particle is being destroyed.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 41


def test_destructor_at_top_level(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("this particle is being destroyed.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 33


def test_truncated_destructor_phrase_in_trigger_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 22


def test_destructor_block_missing_and_it_does(parse: Parse):
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is being destroyed.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 6


def test_destructor_action_block_missing_close_brace(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is being destroyed.\n"
        + "    } and it does {\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=67
    )
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=1),
            expected_indent=4,
            actual_indent=0,
        )
    ]
