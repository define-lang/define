# pyright: reportUnusedCallResult=false
"""Quality Implication Statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse

# --- Successful parses ---


def test_implication_with_action_name_type(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the action</required>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [implication] = definition.quality_implications
    typed_name = implication.typed_global_name
    assert typed_name.name_type == name_types.NameType.ACTION
    assert typed_name.name_content.path.name == "/required"
    assert implication.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=42
    )


def test_implication_with_various_fqun_forms(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position<mv:example.com:my_lib:/full>.\n"
        + "    it also assigns the position<example.com:my_lib:/short_mv>.\n"
        + "    it also assigns the position<standard:/std>.\n"
        + "    it also assigns the position</local>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [full, short_multiverse, universe_only, path_only] = definition.quality_implications
    full_name = full.typed_global_name
    full_fqun = full_name.name_content.fqun
    assert full_fqun is not None
    assert full_fqun.multiverse is not None
    assert full_fqun.multiverse.name == "mv"
    assert full_fqun.multiverse.location == ast.SourceLocation(
        line=2, column=34, end_line=2, end_column=35
    )
    assert full_fqun.authority is not None
    assert full_fqun.authority.name == "example.com"
    assert full_fqun.authority.location == ast.SourceLocation(
        line=2, column=37, end_line=2, end_column=47
    )
    assert full_fqun.universe.name == "my_lib"
    assert full_fqun.universe.location == ast.SourceLocation(
        line=2, column=49, end_line=2, end_column=54
    )
    assert full_fqun.location == ast.SourceLocation(
        line=2, column=34, end_line=2, end_column=54
    )
    assert full_name.name_content.path.name == "/full"
    short_multiverse_name = short_multiverse.typed_global_name
    short_multiverse_fqun = short_multiverse_name.name_content.fqun
    assert short_multiverse_fqun is not None
    assert short_multiverse_fqun.multiverse is None
    assert short_multiverse_fqun.authority is not None
    assert short_multiverse_fqun.authority.name == "example.com"
    assert short_multiverse_fqun.authority.location == ast.SourceLocation(
        line=3, column=34, end_line=3, end_column=44
    )
    assert short_multiverse_fqun.universe.name == "my_lib"
    assert short_multiverse_fqun.universe.location == ast.SourceLocation(
        line=3, column=46, end_line=3, end_column=51
    )
    assert short_multiverse_fqun.location == ast.SourceLocation(
        line=3, column=34, end_line=3, end_column=51
    )
    assert short_multiverse_name.name_content.path.name == "/short_mv"
    universe_only_name = universe_only.typed_global_name
    universe_only_fqun = universe_only_name.name_content.fqun
    assert universe_only_fqun is not None
    assert universe_only_fqun.multiverse is None
    assert universe_only_fqun.authority is None
    assert universe_only_fqun.universe.name == "standard"
    assert universe_only_fqun.universe.location == ast.SourceLocation(
        line=4, column=34, end_line=4, end_column=41
    )
    assert universe_only_fqun.location == ast.SourceLocation(
        line=4, column=34, end_line=4, end_column=41
    )
    assert universe_only_name.name_content.path.name == "/std"
    path_only_name = path_only.typed_global_name
    assert path_only_name.name_content.fqun is None
    assert path_only_name.enclosing_fqun.canonical == "mv:define-lang.org:parser"
    assert path_only_name.name_content.path.name == "/local"


def test_implication_in_action_before_local_position(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [implication] = definition.quality_implications
    typed_name = implication.typed_global_name
    assert typed_name.name_content.path.name == "/required"
    assert implication.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=44
    )
    [position] = definition.interface_positions
    assert position.typed_name.name_content.name == "run"


def test_implication_in_action_with_no_local_positions(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.\n"
        + "    it happens when {\n"
        + "        the position<some_local> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [implication] = definition.quality_implications
    typed_name = implication.typed_global_name
    assert typed_name.name_content.path.name == "/required"
    assert implication.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=44
    )
    assert definition.interface_positions == ()


def test_multiple_implications_in_action_before_multiple_local_positions(
    parse: Parse,
):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</first>.\n"
        + "    it also assigns the action</second>.\n"
        + "    define the position<run>.\n"
        + "    define the position<other>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first, second] = definition.quality_implications
    first_name = first.typed_global_name
    assert first_name.name_content.path.name == "/first"
    assert first.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=41
    )
    second_name = second.typed_global_name
    assert second_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=40
    )
    [run_position, other_position] = definition.interface_positions
    assert run_position.typed_name.name_content.name == "run"
    assert other_position.typed_name.name_content.name == "other"


def test_implication_with_comments_and_blank_lines(parse: Parse):
    program = parse(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    # leading comment\n"
        + "    it also assigns the position</first>.\n"
        + "\n"
        + "    # between implications\n"
        + "    it also assigns the action</second>.\n"
        + "\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first, second] = definition.quality_implications
    first_name = first.typed_global_name
    assert first_name.name_content.path.name == "/first"
    assert first.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=41
    )
    second_name = second.typed_global_name
    assert second_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=6, column=5, end_line=6, end_column=40
    )


# --- Statement-level syntax errors ---


def test_implication_missing_open_angle_at_eol(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 33
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 33


def test_implication_missing_open_angle_with_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 33
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 33


def test_implication_missing_open_angle_with_trailing_space(parse: Parse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position .\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 33
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 33


def test_implication_empty_name(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position<>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 34
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 34


def test_implication_newline_inside_name(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position<\n"
            + "        /required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 34
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 34


def test_implication_missing_close_angle(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</required.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 44
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 44


def test_implication_missing_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</required>\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 44
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 44


def test_implication_missing_newline_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</required>.    it also assigns the position</other>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 45
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 45


def test_implication_missing_space_after_keyword(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns theposition</required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 24
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 31


def test_implication_extra_space_after_keyword(parse: Parse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the  position</required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 24
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 25


def test_implication_local_name_where_global_required(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidGlobalName) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position<foo>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 34
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 36


def test_implication_chained_name_not_allowed(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</a>::position</b>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 37
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 37


# --- Block-level placement errors ---


def test_implication_after_quality_assignment_block_in_potential_position(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "    }\n"
            + "    it also assigns the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 44


def test_implication_after_local_position_in_action_block(parse: Parse):
    with pytest.raises(parser_exceptions.QualityImplicationInWrongOrder) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it also assigns the position</required>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 23


def test_implication_after_trigger_conditions_block_in_action(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 48


def test_implication_inside_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidPositionConstraintBlock) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</implied>.\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 48


def test_implication_inside_action_statements_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        it also assigns the position</required>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 48


def test_implication_inside_trigger_conditions_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidTriggerConditionsBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        it also assigns the position</required>.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 48


def test_implication_inside_local_position_definition_quality_assignment_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvalidPositionConstraintBlock) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<inner> {\n"
            + "        it may only contain particles where {\n"
            + "            it also assigns the position</required>.\n"
            + "        }\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<inner> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 13
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 52


def test_implication_at_global_scope(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse(
            "it also assigns the position</required>.\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 40


# --- Block content errors ---


def test_implication_only_in_action_definition_block(parse: Parse):
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</required>.\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 1


def test_quality_implication_ends_after_keyword(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedPositionOrAction) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 24
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 24
