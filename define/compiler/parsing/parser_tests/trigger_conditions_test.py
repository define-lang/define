# pyright: reportUnusedCallResult=false
"""Trigger condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


def test_trigger_condition_with_local_position(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=44
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "my_pos"


def test_trigger_condition_with_comments(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        # a comment\n"
        + "        the position<run> has a particle.\n"
        + "        # another comment\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.location == ast.SourceLocation(
        line=5, column=9, end_line=5, end_column=41
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "run"


def test_trigger_condition_with_blank_lines(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "\n"
        + "        the position<run> has a particle.\n"
        + "\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.location == ast.SourceLocation(
        line=5, column=9, end_line=5, end_column=41
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "run"


def test_chained_name_is_parse_error(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.ChainedNameInPositionPresenceStatement
    ) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>::position</other> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 27


def test_global_name_is_parse_error(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "        the position</some_pos> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 22
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 30


def test_trigger_block_same_line_no_space(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {} and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 22
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 22


def test_trigger_block_same_line_with_space(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterOpenBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when { } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 22
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 22


def test_trigger_block_closing_brace_same_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {}\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 22
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 22


def test_empty_trigger_block_is_error(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTriggerConditionContent) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    it happens when {\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 5


def test_invalid_content_in_trigger_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        nonsense\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 16


def test_missing_terminator_after_trigger_condition(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 41
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 41


def test_missing_space_before_has_a_particle(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 28


def test_missing_has_a_particle(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidHasAParticleSyntax) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 26


def test_comment_trailing_space_in_trigger_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        # comment \n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 18
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 18


def test_comment_trailing_space_after_trigger_condition(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "        # comment \n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 18
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 18


def test_position_presence_ends_after_the(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the  \n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 12
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 12


def test_value_in_position_presence_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the value<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 13
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 17


def test_no_space_after_the_in_position_presence(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        theposition<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 12
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 19


def test_source_ends_in_trigger_conditions_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 21


def test_invisible_character_in_position_presence_name_type(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the posi\u200btion<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 17
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 17
