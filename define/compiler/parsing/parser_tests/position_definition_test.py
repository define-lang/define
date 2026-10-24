# pyright: reportUnusedCallResult=false
"""Position definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_position_definition_parses(parse: Parse):
    program = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
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
    assert definition.quality_assignment_block is None


def test_position_definition_locations_have_file_path(parse: Parse):
    file_path = PurePosixPath("library/positions.def")
    program = parse("define the potential position<standard:/path>.\n", file_path)
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=46, file_path=file_path
    )
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=45, file_path=file_path
    )


def test_position_definition_with_non_ascii_path(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/caf\u00e9>.\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    path = definition.typed_name.name_content.path
    assert path.name == "/caf\u00e9"
    assert path.location == ast.SourceLocation(
        line=1, column=57, end_line=1, end_column=61
    )
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=62
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )


def test_position_definition_with_non_ascii_fqun_components(
    parse: Parse,
):
    program = parse(
        "define the potential position<m\u00fc:d\u00e9fine.org:pars\u00e9r:/path>.\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    fqun = definition.typed_name.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "m\u00fc"
    assert fqun.multiverse.location == ast.SourceLocation(
        line=1, column=31, end_line=1, end_column=32
    )
    assert fqun.authority is not None
    assert fqun.authority.name == "d\u00e9fine.org"
    assert fqun.authority.location == ast.SourceLocation(
        line=1, column=34, end_line=1, end_column=43
    )
    assert fqun.universe.name == "pars\u00e9r"
    assert fqun.universe.location == ast.SourceLocation(
        line=1, column=45, end_line=1, end_column=50
    )
    path = definition.typed_name.name_content.path
    assert path.location == ast.SourceLocation(
        line=1, column=52, end_line=1, end_column=56
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=58
    )


def test_position_definition_missing_terminator_after_non_ascii_name(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/caf\u00e9>\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 63


def test_quality_assignment_with_non_ascii_name(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</\u00e9t\u00e9>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert (
        quality_assignment.typed_global_name.name_content.path.name == "/\u00e9t\u00e9"
    )
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=34
    )


def test_position_definition_with_invisible_character_in_invalid_name(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<a\u200bb>.\n")
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 32
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 32


def test_position_definition_with_empty_fqun(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 36


def test_position_definition_with_local_style_name_is_global_terminal(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<foo>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 33


def test_position_definition_missing_open_angle(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential positionstandard:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 30


def test_position_definition_space_instead_of_open_angle(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse("define the potential position mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 30


def test_position_definition_with_control_character(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential \x00position<mv:define-lang.org:parser:/path>.\n")
    assert exc_info.value.char == "\x00"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 22
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 22


def test_position_definition_with_control_character_in_name(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/a\x01b>.\n")
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_position_definition_with_empty_global_path(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 56


def test_position_definition_without_fqun(parse: Parse):
    with pytest.raises(
        parser_exceptions.DefinitionGlobalNameContentRequiresFqun
    ) as exc_info:
        parse("define the potential position</path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 35


def test_position_definition_with_too_many_fqun_components(parse: Parse):
    with pytest.raises(parser_exceptions.GlobalNameInvalidFqunFormat) as exc_info:
        parse("define the potential position<a:b:c:d:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 37


def test_position_definition_with_global_path_missing_leading_slash(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 60


def test_position_definition_empty_name_content(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse("define the potential position<>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_position_definition_empty_name_at_eof(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse("define the potential position<")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_position_definition_with_quality_assignment_block(parse: Parse):
    program = parse(
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
    assert definition.quality_assignment_block is not None
    assert definition.quality_assignment_block.location == ast.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )
    assert (
        quality_assignment.typed_global_name.name_type == name_types.NameType.POSITION
    )
    assert quality_assignment.typed_global_name.name_content.path.name == "/child"


def test_position_definition_with_multiple_quality_assignments(parse: Parse):
    program = parse(
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
    assert definition.quality_assignment_block is not None
    assert definition.quality_assignment_block.location == ast.SourceLocation(
        line=2, column=5, end_line=5, end_column=5
    )
    [first, second] = definition.quality_assignment_block.statements
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


def test_position_definition_block_requires_content(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path> {\n}\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_quality_assignment_block_requires_statements(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingQualityAssignmentBlockContent
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 5


def test_quality_assignment_block_with_invalid_statement_then_more_definitions(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidQualityAssignmentBlock) as exc_info:
        parse(
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


def test_position_definition_rejects_multiple_quality_assignment_blocks(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
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


def test_second_quality_assignment_block_after_close_on_same_line(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        parse(
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


def test_second_quality_assignment_block_on_quality_assignment_line(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
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
    program = parse(
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
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [run, empty_pos, constrained_pos] = definition.interface_positions
    assert run.typed_name.name_type == name_types.NameType.POSITION
    assert run.typed_name.name_content.name == "run"
    assert run.quality_assignment_block is None
    assert run.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=29
    )
    assert empty_pos.typed_name.name_type == name_types.NameType.POSITION
    assert empty_pos.typed_name.name_content.name == "empty_pos"
    assert empty_pos.quality_assignment_block is None
    assert empty_pos.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=35
    )
    assert constrained_pos.typed_name.name_type == name_types.NameType.POSITION
    assert constrained_pos.typed_name.name_content.name == "constrained_pos"
    assert constrained_pos.quality_assignment_block is not None
    [quality_assignment] = constrained_pos.quality_assignment_block.statements
    assert (
        quality_assignment.typed_global_name.name_type == name_types.NameType.POSITION
    )
    assert quality_assignment.typed_global_name.name_content.fqun is None
    assert quality_assignment.typed_global_name.name_content.path.name == "/child"
    assert constrained_pos.location == ast.SourceLocation(
        line=4, column=5, end_line=8, end_column=5
    )


def test_action_definition_block_with_multiple_local_block_positions(
    parse: Parse,
):
    program = parse(
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
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [run, first_pos, second_pos] = definition.interface_positions
    assert run.typed_name.name_type == name_types.NameType.POSITION
    assert run.typed_name.name_content.name == "run"
    assert run.quality_assignment_block is None
    assert run.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=29
    )
    assert first_pos.typed_name.name_type == name_types.NameType.POSITION
    assert first_pos.typed_name.name_content.name == "first_pos"
    assert first_pos.quality_assignment_block is not None
    [first_quality_assignment] = first_pos.quality_assignment_block.statements
    assert (
        first_quality_assignment.typed_global_name.name_type
        == name_types.NameType.POSITION
    )
    assert first_quality_assignment.typed_global_name.name_content.fqun is None
    assert (
        first_quality_assignment.typed_global_name.name_content.path.name
        == "/first_child"
    )
    assert first_pos.location == ast.SourceLocation(
        line=3, column=5, end_line=7, end_column=5
    )
    assert second_pos.typed_name.name_type == name_types.NameType.POSITION
    assert second_pos.typed_name.name_content.name == "second_pos"
    assert second_pos.quality_assignment_block is not None
    [second_quality_assignment] = second_pos.quality_assignment_block.statements
    assert (
        second_quality_assignment.typed_global_name.name_type
        == name_types.NameType.ACTION
    )
    assert second_quality_assignment.typed_global_name.name_content.fqun is None
    assert (
        second_quality_assignment.typed_global_name.name_content.path.name
        == "/second_child"
    )
    assert second_pos.location == ast.SourceLocation(
        line=8, column=5, end_line=12, end_column=5
    )


def test_action_statements_block_with_mixed_local_position_forms(
    parse: Parse,
):
    program = parse(
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
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [empty_inner, constrained_inner] = definition.action_statements.statements
    assert isinstance(empty_inner, ast.LocalPositionDefinition)
    assert empty_inner.typed_name.name_type == name_types.NameType.POSITION
    assert empty_inner.typed_name.name_content.name == "empty_inner"
    assert empty_inner.quality_assignment_block is None
    assert empty_inner.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=41
    )
    assert isinstance(constrained_inner, ast.LocalPositionDefinition)
    assert constrained_inner.typed_name.name_type == name_types.NameType.POSITION
    assert constrained_inner.typed_name.name_content.name == "constrained_inner"
    assert constrained_inner.quality_assignment_block is not None
    [quality_assignment] = constrained_inner.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_type == name_types.NameType.ACTION
    assert quality_assignment.typed_global_name.name_content.fqun is None
    assert (
        quality_assignment.typed_global_name.name_content.path.name == "/inner_action"
    )
    assert constrained_inner.location == ast.SourceLocation(
        line=7, column=9, end_line=11, end_column=9
    )


def test_action_statements_block_with_multiple_local_block_positions(
    parse: Parse,
):
    program = parse(
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
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first_inner, second_inner] = definition.action_statements.statements
    assert isinstance(first_inner, ast.LocalPositionDefinition)
    assert first_inner.typed_name.name_type == name_types.NameType.POSITION
    assert first_inner.typed_name.name_content.name == "first_inner"
    assert first_inner.quality_assignment_block is not None
    [first_quality_assignment] = first_inner.quality_assignment_block.statements
    assert (
        first_quality_assignment.typed_global_name.name_type
        == name_types.NameType.POSITION
    )
    assert first_quality_assignment.typed_global_name.name_content.fqun is None
    assert (
        first_quality_assignment.typed_global_name.name_content.path.name
        == "/first_child"
    )
    assert first_inner.location == ast.SourceLocation(
        line=6, column=9, end_line=10, end_column=9
    )
    assert isinstance(second_inner, ast.LocalPositionDefinition)
    assert second_inner.typed_name.name_type == name_types.NameType.POSITION
    assert second_inner.typed_name.name_content.name == "second_inner"
    assert second_inner.quality_assignment_block is not None
    [second_quality_assignment] = second_inner.quality_assignment_block.statements
    assert (
        second_quality_assignment.typed_global_name.name_type
        == name_types.NameType.ACTION
    )
    assert second_quality_assignment.typed_global_name.name_content.fqun is None
    assert (
        second_quality_assignment.typed_global_name.name_content.path.name
        == "/second_child"
    )
    assert second_inner.location == ast.SourceLocation(
        line=11, column=9, end_line=15, end_column=9
    )


def test_empty_potential_position_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse("define the potential position<standard:/path> {\n}\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_invalid_content_in_potential_position_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    nonsense here\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 17


def test_quality_implication_in_potential_position_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidPositionDefinitionBlock) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it also assigns the position</required>.\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 44


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
    assert exc_info.value.location.end_line == 3
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
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 21


def test_text_where_local_position_terminator_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run> x\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 29
