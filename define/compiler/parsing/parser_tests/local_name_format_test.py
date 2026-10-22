# pyright: reportUnusedCallResult=false
"""Local name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse


def test_local_name_simple(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "my_pos"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=30
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "my_pos"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=27
    )


def test_local_name_underscore_start(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_private>.\n"
        + "    it happens when {\n"
        + "        the position<_private> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "_private"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=32
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "_private"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=29
    )


def test_local_name_with_digits(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<pos_1>.\n"
        + "    it happens when {\n"
        + "        the position<pos_1> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "pos_1"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=29
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "pos_1"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=26
    )


def test_local_name_single_char(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<x>.\n"
        + "    it happens when {\n"
        + "        the position<x> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "x"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=25
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "x"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=22
    )


def test_local_name_single_underscore(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<_>.\n"
        + "    it happens when {\n"
        + "        the position<_> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "_"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=25
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "_"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=22
    )


def test_local_name_starting_with_digit(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<2bad>.\n"
        + "    it happens when {\n"
        + "        the position<2bad> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "2bad"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=28
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "2bad"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=25
    )


def test_local_name_uppercase(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<MyPos>.\n"
        + "    it happens when {\n"
        + "        the position<MyPos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "MyPos"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=29
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "MyPos"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=26
    )


def test_local_name_with_space(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position< >.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 25


def test_local_name_with_space_after_valid_characters(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<test path>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.name == "test"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 29


def test_create_position_ref_starting_with_space(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidName) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in position< :/x>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.token == " "
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 39
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 39


def test_local_name_first_char_colon(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<:>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 25


def test_local_name_first_char_slash(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position</>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 25


def test_local_name_missing_open_angle(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the positionmy_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 24
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 24


def test_local_name_empty(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 25


def test_local_name_with_angle_bracket(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<<>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [_, position] = definition.interface_positions
    assert position.typed_name.name_content.name == "<"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=3, column=25, end_line=3, end_column=25
    )


def test_local_name_dot_then_angle_bracket(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<.<>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [_, position] = definition.interface_positions
    assert position.typed_name.name_content.name == ".<"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=3, column=25, end_line=3, end_column=26
    )


def test_local_name_dot_then_slash(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<./>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 26


def test_local_name_brace_then_slash(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<}/>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 26


def test_local_name_angle_bracket_then_slash(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<</>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "/"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 26


def test_local_name_angle_bracket_then_colon(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<<:>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 26


def test_local_name_with_slash(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<my/pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 27
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 27


def test_local_name_with_colon(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidLocalNameCharacter) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<my:pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == ":"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 27
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 27


def test_local_name_with_global_short_form(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position</mypos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 30


def test_local_name_with_global_long_form(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.GlobalNameWhereLocalNameExpected) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    define the position<mv:define-lang.org:other_universe:/mypos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 25
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 64


def test_local_name_with_hyphen(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<my-pos>.\n"
        + "    it happens when {\n"
        + "        the position<my-pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "my-pos"
    assert position.typed_name.name_content.location == ast.SourceLocation(
        line=2, column=25, end_line=2, end_column=30
    )
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_content.name == "my-pos"
    assert condition.typed_name.name_content.location == ast.SourceLocation(
        line=4, column=22, end_line=4, end_column=27
    )
