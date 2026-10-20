# pyright: reportUnusedCallResult=false
"""Position definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_position_definition_parses(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )
    assert definition.typed_name.name_type == name_types.NameType.POSITION
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=62
    )
    assert definition.quality_implications == ()
    assert definition.constraints is None


def test_position_definition_with_local_style_name_is_global_terminal(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        native_parse("define the potential position<foo>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 33


def test_position_definition_missing_open_angle(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential positionstandard:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_column == 43
    assert exc_info.value.name == "standard:/path"


def test_position_definition_space_instead_of_open_angle(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential position mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.name == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_column == 30


def test_position_definition_with_control_character(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential \x00position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 6


def test_position_definition_with_empty_global_path(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        native_parse("define the potential position<mv:define-lang.org:parser:>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 56


def test_position_definition_without_fqun(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.DefinitionGlobalNameContentRequiresFqun
    ) as exc_info:
        native_parse("define the potential position</path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 35


def test_position_definition_with_too_many_fqun_components(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.GlobalNameInvalidFqunFormat) as exc_info:
        native_parse("define the potential position<a:b:c:d:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 37


def test_position_definition_with_global_path_missing_leading_slash(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        native_parse("define the potential position<mv:define-lang.org:parser:path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 60


def test_position_definition_empty_name_content(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        native_parse("define the potential position<>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_position_definition_empty_name_at_eof(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        native_parse("define the potential position<")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_position_definition_with_constraint_block(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )
    assert definition.quality_implications == ()
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )
    [requirement] = definition.constraints.requirements
    assert requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )
    assert requirement.typed_global_name.name_type == name_types.NameType.POSITION
    assert requirement.typed_global_name.name_content.path.name == "/child"


def test_position_definition_with_multiple_requirements(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first>.\n"
        + "        it has the action</second>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=6, end_column=1
    )
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=2, column=5, end_line=5, end_column=5
    )
    [first, second] = definition.constraints.requirements
    assert first.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )
    assert first.typed_global_name.name_type == name_types.NameType.POSITION
    assert first.typed_global_name.name_content.path.name == "/first"
    assert second.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=35
    )
    assert second.typed_global_name.name_type == name_types.NameType.ACTION
    assert second.typed_global_name.name_content.path.name == "/second"


def test_position_definition_block_requires_content(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_position_constraint_block_requires_requirements(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingPositionConstraintContent) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 5


def test_position_constraint_block_with_invalid_statement_then_more_definitions(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidPositionConstraintBlock) as exc_info:
        native_parse(
            "define the potential position<my_lib:/path>.\n"
            + "define the potential position<my_lib:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        t has the position<my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 41


def test_position_definition_rejects_multiple_constraint_blocks(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.\n"
            + "    }\n"
            + "    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 41


def test_second_constraint_block_after_close_on_same_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.\n"
            + "    }    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 6


def test_second_constraint_block_on_requirement_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</first>.    it may only contain particles where {\n"
            + "        it has the action</second>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 37
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 37


def test_action_definition_block_with_mixed_local_position_forms(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<empty_pos>.\n"
        + "    define the position<constrained_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "empty_pos",
        "constrained_pos",
        "run",
    ]


def test_action_definition_block_with_multiple_local_block_positions(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    define the position<first_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</first_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the action</second_child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "first_pos",
        "second_pos",
        "run",
    ]


def test_action_statements_block_with_mixed_local_position_forms(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<empty_inner>.\n"
        + "        define the position<constrained_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the action</inner_action>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/inner_action",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "empty_inner",
        "constrained_inner",
    ]


def test_action_statements_block_with_multiple_local_block_positions(
    parse: Parse,
):
    tree = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<first_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the position</first_child>.\n"
        + "            }\n"
        + "        }\n"
        + "        define the position<second_inner> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the action</second_child>.\n"
        + "            }\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/act",
        "/first_child",
        "/second_child",
    ]
    assert get_tokens_by_type(tree, "LOCAL_NAME_CONTENT") == [
        "run",
        "run",
        "first_inner",
        "second_inner",
    ]


def test_empty_potential_position_block(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.MissingPotentialPositionDefinitionContent
    ) as exc_info:
        native_parse("define the potential position<standard:/path> {\n}\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_invalid_content_in_potential_position_block(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.InvalidPotentialPositionDefinitionBlock
    ) as exc_info:
        native_parse(
            "define the potential position<standard:/path> {\n"
            + "    nonsense here\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 17


def test_empty_local_position_definition_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse(
            "define the potential action<standard:/act> {\n"
            + "    define the position<bad> {\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<bad> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_column == 5


def test_invalid_content_in_local_position_definition_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        parse(
            "define the potential action<standard:/act> {\n"
            + "    define the position<bad> {\n"
            + "        nonsense here\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<bad> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_column == 16
