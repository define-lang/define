# pyright: reportUnusedCallResult=false
"""Action definition parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        NativeParse,
        NativeParseWithDiagnostics,
    )


def test_action_definition_without_body_is_error(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingOpenBrace) as exc_info:
        native_parse("define the potential action<standard:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 44
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 44


def test_action_definition_with_body_parses(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<standard:/path> {\n"
        + "    define the position<pp>.\n"
        + "    it happens when {\n"
        + "        the position<pp> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<noop>.\n"
        + "        create a particle in position<noop>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.typed_name.name_type == name_types.NameType.ACTION
    assert definition.typed_name.name_content.path.name == "/path"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=9, end_column=1
    )


def test_action_definition_missing_open_angle(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingOpenAngleBracket) as exc_info:
        native_parse("define the potential actionstandard:/path>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 28
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 28


def test_action_definition_empty_name_content(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyName) as exc_info:
        native_parse("define the potential action<>.\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 29


def test_action_with_empty_inner_blocks(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.action_statements.statements == ()
    assert definition.action_statements.location == ast.SourceLocation(
        line=5, column=7, end_line=6, end_column=5
    )


def test_action_with_local_position_definition(native_parse: NativeParse):
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
    [position] = definition.interface_positions
    assert position.typed_name.name_type == name_types.NameType.POSITION
    assert position.typed_name.name_content.name == "my_pos"
    assert position.constraints is None
    assert position.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=32
    )


def test_action_with_constrained_local_position_definition(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the action</do_work>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_type == name_types.NameType.POSITION
    assert position.typed_name.name_content.name == "my_pos"
    assert position.constraints is not None
    [requirement] = position.constraints.requirements
    assert requirement.typed_global_name.name_type == name_types.NameType.ACTION
    assert requirement.typed_global_name.name_content.fqun is None
    assert requirement.typed_global_name.name_content.path.name == "/do_work"
    assert position.location == ast.SourceLocation(
        line=2, column=5, end_line=6, end_column=5
    )


def test_action_with_multiple_local_position_definitions(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos>.\n"
        + "    it happens when {\n"
        + "        the position<first_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first_position, second_position] = definition.interface_positions
    assert first_position.typed_name.name_type == name_types.NameType.POSITION
    assert first_position.typed_name.name_content.name == "first_pos"
    assert first_position.constraints is None
    assert first_position.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=35
    )
    assert second_position.typed_name.name_type == name_types.NameType.POSITION
    assert second_position.typed_name.name_content.name == "second_pos"
    assert second_position.constraints is None
    assert second_position.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=36
    )


def test_action_with_mixed_local_position_definition_forms(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<first_pos>.\n"
        + "    define the position<second_pos> {\n"
        + "        it may only contain particles where {\n"
        + "            it has the position</child>.\n"
        + "        }\n"
        + "    }\n"
        + "    it happens when {\n"
        + "        the position<first_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first_position, second_position] = definition.interface_positions
    assert first_position.typed_name.name_type == name_types.NameType.POSITION
    assert first_position.typed_name.name_content.name == "first_pos"
    assert first_position.constraints is None
    assert first_position.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=35
    )
    assert second_position.typed_name.name_type == name_types.NameType.POSITION
    assert second_position.typed_name.name_content.name == "second_pos"
    assert second_position.constraints is not None
    [requirement] = second_position.constraints.requirements
    assert requirement.typed_global_name.name_type == name_types.NameType.POSITION
    assert requirement.typed_global_name.name_content.fqun is None
    assert requirement.typed_global_name.name_content.path.name == "/child"
    assert second_position.location == ast.SourceLocation(
        line=3, column=5, end_line=7, end_column=5
    )


def test_action_block_with_comments_and_blank_lines(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<my_pos>.\n"
        + "\n"
        + "    # a comment\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_type == name_types.NameType.POSITION
    assert position.typed_name.name_content.name == "my_pos"
    assert definition.trigger_conditions.location == ast.SourceLocation(
        line=5, column=5, end_line=7, end_column=5
    )


def test_action_block_with_full_fqun(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/some/path> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    typed_name = definition.typed_name
    assert typed_name.name_type == name_types.NameType.ACTION
    fqun = typed_name.name_content.fqun
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert typed_name.name_content.path.name == "/some/path"
    assert typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=65
    )


def test_action_block_comment_after_trigger_open(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when { # comment\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_type == name_types.NameType.POSITION
    assert condition.typed_name.name_content.name == "run"
    assert condition.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=41
    )


def test_action_block_comment_after_action_close(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    } # comment\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.action_statements.statements == ()
    assert definition.action_statements.location == ast.SourceLocation(
        line=5, column=7, end_line=6, end_column=5
    )


def test_action_block_no_indentation(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "define the position<run>.\n"
        + "it happens when {\n"
        + "the position<run> has a particle.\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=4, column=1, end_line=4, end_column=1),
            expected_indent=4,
            actual_indent=0,
        ),
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_type == name_types.NameType.POSITION
    assert position.typed_name.name_content.name == "run"
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.typed_name.name_type == name_types.NameType.POSITION
    assert condition.typed_name.name_content.name == "run"
    assert definition.action_statements.statements == ()


def test_action_block_blank_lines_in_trigger_block(native_parse: NativeParse):
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
    assert condition.typed_name.name_type == name_types.NameType.POSITION
    assert condition.typed_name.name_content.name == "run"
    assert condition.location == ast.SourceLocation(
        line=5, column=9, end_line=5, end_column=41
    )


def test_action_block_blank_lines_in_action_block(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "\n"
        + "\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    assert definition.action_statements.statements == ()
    assert definition.action_statements.location == ast.SourceLocation(
        line=5, column=7, end_line=8, end_column=5
    )


def test_action_block_with_local_position_definition_in_action_statements(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.LocalPositionDefinition)
    assert statement.typed_name.name_type == name_types.NameType.POSITION
    assert statement.typed_name.name_content.name == "inner_pos"
    assert statement.constraints is None
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=39
    )


def test_action_block_with_multiple_local_position_definitions_in_action_statements(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<first_inner>.\n"
        + "        define the position<second_inner>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [first_statement, second_statement] = definition.action_statements.statements
    assert isinstance(first_statement, ast.LocalPositionDefinition)
    assert first_statement.typed_name.name_type == name_types.NameType.POSITION
    assert first_statement.typed_name.name_content.name == "first_inner"
    assert first_statement.constraints is None
    assert first_statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=41
    )
    assert isinstance(second_statement, ast.LocalPositionDefinition)
    assert second_statement.typed_name.name_type == name_types.NameType.POSITION
    assert second_statement.typed_name.name_content.name == "second_inner"
    assert second_statement.constraints is None
    assert second_statement.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=42
    )


def test_action_block_with_local_position_definitions_inside_and_outside_action_statements(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<outer_pos>.\n"
        + "    it happens when {\n"
        + "        the position<outer_pos> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position] = definition.interface_positions
    assert position.typed_name.name_type == name_types.NameType.POSITION
    assert position.typed_name.name_content.name == "outer_pos"
    assert position.constraints is None
    assert position.location == ast.SourceLocation(
        line=2, column=5, end_line=2, end_column=35
    )
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.LocalPositionDefinition)
    assert statement.typed_name.name_type == name_types.NameType.POSITION
    assert statement.typed_name.name_content.name == "inner_pos"
    assert statement.constraints is None
    assert statement.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=39
    )


def test_two_action_definitions_in_same_file(native_parse: NativeParse):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/first> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
        + "define the potential action<mv:define-lang.org:parser:/second> {\n"
        + "    define the position<my_pos>.\n"
        + "    it happens when {\n"
        + "        the position<my_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    [first_definition, second_definition] = program.definitions
    assert isinstance(first_definition, ast.ActionDefinition)
    assert first_definition.typed_name.name_type == name_types.NameType.ACTION
    assert first_definition.typed_name.name_content.path.name == "/first"
    assert first_definition.location == ast.SourceLocation(
        line=1, column=1, end_line=7, end_column=1
    )
    assert isinstance(second_definition, ast.ActionDefinition)
    assert second_definition.typed_name.name_type == name_types.NameType.ACTION
    assert second_definition.typed_name.name_content.path.name == "/second"
    assert second_definition.location == ast.SourceLocation(
        line=8, column=1, end_line=14, end_column=1
    )


def test_action_block_missing_trigger_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<my_pos>.\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 1


def test_global_position_definition_not_allowed_in_action_definition_block(
    native_parse: NativeParse,
):
    with pytest.raises(
        parser_exceptions.GlobalPositionDefinitionInLocalContext
    ) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 33


def test_global_position_definition_not_allowed_in_action_statements_block(
    native_parse: NativeParse,
):
    with pytest.raises(
        parser_exceptions.GlobalPositionDefinitionInLocalContext
    ) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        define the potential position<mv:define-lang.org:parser:/inner_pos>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 37


def test_action_block_missing_action_statements_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 6


def test_action_block_missing_outer_close(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 67


def test_action_block_extra_space_before_brace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExtraWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/path>  {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 61
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 62


def test_action_block_no_newline_after_open_brace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/path> {}\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 63


def test_action_block_missing_newline_after_outer_open_brace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterOpenBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/path> { it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 63
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 63


def test_action_block_missing_newline_after_inner_close(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 6


def test_trigger_and_action_on_wrong_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }\n"
            + "    and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 6


def test_local_position_after_trigger_and_action(native_parse: NativeParse):
    with pytest.raises(
        parser_exceptions.InvalidPositionDefinitionLocationInAction
    ) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    define the position<late_pos>.\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 7
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 7
    assert exc_info.value.location.end_column == 23


def test_second_trigger_and_action_block_pair_not_allowed(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 7
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 7
    assert exc_info.value.location.end_column == 21


def test_missing_close_brace_followed_by_global_definition(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "define the potential position<mv:define-lang.org:parser:/my_action>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=67
    )
    assert result.diagnostics == []


def test_trigger_conditions_block_missing_close_brace_followed_by_global_definition(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "define the potential position<mv:define-lang.org:parser:/other>.\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=21
    )
    assert result.diagnostics == []


def test_action_statements_block_invalid_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        nonsense\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 16


def test_action_statements_block_with_create_particle_local_position(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [typed_name] = statement.target_position.typed_names
    assert isinstance(typed_name, ast.LocalTypedNameReference)
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=42
    )


def test_action_statements_block_with_create_particle_short_global_position(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [typed_name] = statement.target_position.typed_names
    assert isinstance(typed_name, ast.GlobalTypedNameReference)
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.fqun is None
    assert typed_name.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=43
    )


def test_action_statements_block_with_create_particle_full_global_position(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<mv:define-lang.org:parser:/run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [typed_name] = statement.target_position.typed_names
    assert isinstance(typed_name, ast.GlobalTypedNameReference)
    assert typed_name.name_type == name_types.NameType.POSITION
    fqun = typed_name.name_content.fqun
    assert fqun is not None
    assert fqun.multiverse is not None
    assert fqun.multiverse.name == "mv"
    assert fqun.authority is not None
    assert fqun.authority.name == "define-lang.org"
    assert fqun.universe.name == "parser"
    assert typed_name.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=69
    )


def test_action_statements_block_with_create_particle_chain(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<to>::action</deposit>::position<run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [to, deposit, run] = statement.target_position.typed_names
    assert isinstance(to, ast.LocalTypedNameReference)
    assert to.name_type == name_types.NameType.POSITION
    assert to.name_content.name == "to"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(run, ast.LocalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.name == "run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=74
    )


def test_action_statements_block_with_create_particle_short_global_chain(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position</to>::action</deposit>::position</run>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [to, deposit, run] = statement.target_position.typed_names
    assert isinstance(to, ast.GlobalTypedNameReference)
    assert to.name_type == name_types.NameType.POSITION
    assert to.name_content.fqun is None
    assert to.name_content.path.name == "/to"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(run, ast.GlobalTypedNameReference)
    assert run.name_type == name_types.NameType.POSITION
    assert run.name_content.fqun is None
    assert run.name_content.path.name == "/run"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=76
    )


def test_action_statements_block_with_create_particle_any_typed_chain(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in action</start>::position<mid>::action</end>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [statement] = definition.action_statements.statements
    assert isinstance(statement, ast.CreateParticleStatement)
    [start, mid, end] = statement.target_position.typed_names
    assert isinstance(start, ast.GlobalTypedNameReference)
    assert start.name_type == name_types.NameType.ACTION
    assert start.name_content.fqun is None
    assert start.name_content.path.name == "/start"
    assert isinstance(mid, ast.LocalTypedNameReference)
    assert mid.name_type == name_types.NameType.POSITION
    assert mid.name_content.name == "mid"
    assert isinstance(end, ast.GlobalTypedNameReference)
    assert end.name_type == name_types.NameType.ACTION
    assert end.name_content.fqun is None
    assert end.name_content.path.name == "/end"
    assert statement.target_position.location == ast.SourceLocation(
        line=6, column=30, end_line=6, end_column=72
    )


def test_action_statements_block_with_mixed_statements_and_multiple_create_particles(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<inner_pos>.\n"
        + "        create a particle in position<inner_pos>.\n"
        + "        create a particle in position</global_run>::action</deposit>::position<inner_pos>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [position_definition, first_create, second_create] = (
        definition.action_statements.statements
    )
    assert isinstance(position_definition, ast.LocalPositionDefinition)
    assert position_definition.typed_name.name_type == name_types.NameType.POSITION
    assert position_definition.typed_name.name_content.name == "inner_pos"
    assert position_definition.constraints is None
    assert position_definition.location == ast.SourceLocation(
        line=6, column=9, end_line=6, end_column=39
    )
    assert isinstance(first_create, ast.CreateParticleStatement)
    [first_inner_pos] = first_create.target_position.typed_names
    assert isinstance(first_inner_pos, ast.LocalTypedNameReference)
    assert first_inner_pos.name_type == name_types.NameType.POSITION
    assert first_inner_pos.name_content.name == "inner_pos"
    assert first_create.location == ast.SourceLocation(
        line=7, column=9, end_line=7, end_column=49
    )
    assert isinstance(second_create, ast.CreateParticleStatement)
    [global_run, deposit, second_inner_pos] = second_create.target_position.typed_names
    assert isinstance(global_run, ast.GlobalTypedNameReference)
    assert global_run.name_type == name_types.NameType.POSITION
    assert global_run.name_content.fqun is None
    assert global_run.name_content.path.name == "/global_run"
    assert isinstance(deposit, ast.GlobalTypedNameReference)
    assert deposit.name_type == name_types.NameType.ACTION
    assert deposit.name_content.fqun is None
    assert deposit.name_content.path.name == "/deposit"
    assert isinstance(second_inner_pos, ast.LocalTypedNameReference)
    assert second_inner_pos.name_type == name_types.NameType.POSITION
    assert second_inner_pos.name_content.name == "inner_pos"
    assert second_create.location == ast.SourceLocation(
        line=8, column=9, end_line=8, end_column=90
    )


def test_no_space_before_and_it_does(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 8


def test_comment_trailing_space_first_in_action_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    # comment \n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 14
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 14


def test_comment_trailing_space_after_quality_implication(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it also assigns the position</q>.\n"
            + "    # comment \n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 14
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 14


def test_comment_trailing_space_after_interface_position(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    # comment \n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 14
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 14


def test_comment_trailing_space_before_action_close(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "    # comment \n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 7
    assert exc_info.value.location.column == 14
    assert exc_info.value.location.end_line == 7
    assert exc_info.value.location.end_column == 14


def test_text_after_action_close(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "} x\n"
        )
    assert exc_info.value.location.line == 7
    assert exc_info.value.location.column == 2
    assert exc_info.value.location.end_line == 7
    assert exc_info.value.location.end_column == 2


def test_text_after_interface_position_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.x\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 30


def test_no_space_before_trigger_conditions_brace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespaceBeforeBrace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when{\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 20
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 20


def test_comment_trailing_space_in_action_statements_block(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        # comment \n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 18
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 18


def test_missing_space_between_words_of_trigger_conditions_block(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happenswhen {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 18


def test_missing_space_between_words_of_action_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingWhitespace) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        createa particle in position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 15


def test_word_that_starts_like_action_statement_word_is_not_missing_space(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvalidActionStatementsBlock) as exc_info:
        native_parse(
            "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        creates a particle in position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 9
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 44


def test_position_constraint_block_missing_close_brace_followed_by_action_statement(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        define the position<p> {\n"
        + "            it may only contain particles where {\n"
        + "                it has the action</x>.\n"
        + "        create a particle in position<p>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=7, column=13, end_line=7, end_column=49
    )
    assert result.diagnostics == []


def test_trigger_conditions_block_missing_close_brace_followed_by_local_position(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    define the position<other>.\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=3, column=5, end_line=3, end_column=21
    )
    assert result.diagnostics == []


def test_action_statements_block_missing_close_brace_followed_by_implication(
    native_parse_with_diagnostics: NativeParseWithDiagnostics,
):
    result = native_parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        create a particle in position<run>.\n"
        + "    it also assigns the position</q>.\n"
        + "}\n"
    )
    assert isinstance(result.exception, parser_exceptions.MissingCloseBrace)
    assert result.exception.location == ast.SourceLocation(
        line=5, column=7, end_line=5, end_column=19
    )
    assert result.diagnostics == []
