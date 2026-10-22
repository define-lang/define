# pyright: reportUnusedCallResult=false
"""Constructor condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        NativeParse,
        NativeParseWithDiagnostics,
    )


def test_constructor_with_no_interface_positions(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.ConstructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=33
    )
    assert definition.interface_positions == ()


def test_constructor_with_comments(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        this particle is created.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.ConstructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=33
    )


def test_constructor_with_blank_lines(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "\n"
        + "        this particle is created.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.ConstructorConditionStatement)
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=33
    )


def test_constructor_missing_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is created\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 33
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 33


def test_constructor_followed_by_extra_content(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is created now.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 33
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 33


def test_trigger_condition_and_constructor_in_one_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 33


def test_constructor_as_action_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        this particle is created.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 33


def test_constructor_at_top_level(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("this particle is created.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 25


def test_truncated_constructor_phrase_in_trigger_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 25


def test_constructor_block_missing_and_it_does(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 6


def test_constructor_action_block_missing_close_brace(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
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


def test_text_after_trigger_condition_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        this particle is created.x\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 34
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 34
