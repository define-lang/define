# pyright: reportUnusedCallResult=false
"""Block parsing tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import Parse


def test_empty_block_on_position(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse("define the potential position<standard:/path> {\n}\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_empty_block_on_action(parse: Parse):
    with pytest.raises(parser_exceptions.MissingActionDefinitionSyntax) as exc_info:
        parse("define the potential action<standard:/path> {\n}\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_block_with_blank_lines(parse: Parse):
    program = parse(
        "define the potential position<standard:/path> {\n"
        + "\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=7, end_column=1
    )
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=3, column=5, end_line=5, end_column=5
    )
    [requirement] = definition.constraints.requirements
    assert requirement.typed_global_name.full_typed_name == "position<standard:/child>"
    assert requirement.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )


def test_blank_line_between_constraint_requirement_and_close(parse: Parse):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "\n"
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
    [requirement] = definition.constraints.requirements
    assert (
        requirement.typed_global_name.full_typed_name
        == "position<mv:define-lang.org:parser:/child>"
    )
    assert requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )


def test_comment_line_between_constraint_requirement_and_close(
    parse: Parse,
):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "        # trailing note\n"
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
    [requirement] = definition.constraints.requirements
    assert (
        requirement.typed_global_name.full_typed_name
        == "position<mv:define-lang.org:parser:/child>"
    )
    assert requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )


def test_block_with_comment_inside(parse: Parse):
    program = parse(
        "define the potential position<standard:/path> {\n"
        + "    # comment\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=6, end_column=1
    )
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=3, column=5, end_line=5, end_column=5
    )
    [requirement] = definition.constraints.requirements
    assert requirement.typed_global_name.full_typed_name == "position<standard:/child>"
    assert requirement.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )


def test_block_with_comment_after_open(parse: Parse):
    program = parse(
        "define the potential position<standard:/path> { # comment\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )
    [requirement] = definition.constraints.requirements
    assert requirement.typed_global_name.full_typed_name == "position<standard:/child>"
    assert requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )


def test_block_with_comment_after_close(parse: Parse):
    program = parse(
        "define the potential position<standard:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "} # comment\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )
    assert definition.constraints is not None
    assert definition.constraints.location == ast.SourceLocation(
        line=2, column=5, end_line=4, end_column=5
    )
    [requirement] = definition.constraints.requirements
    assert requirement.typed_global_name.full_typed_name == "position<standard:/child>"
    assert requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )


def test_block_with_full_fqun(parse: Parse):
    program = parse(
        "define the potential position<my_mv:example.com:my_lib:/some/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action</some/action>.\n"
        + "    }\n"
        + "}\n"
    )
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert (
        definition.typed_name.full_typed_name
        == "position<my_mv:example.com:my_lib:/some/path>"
    )
    assert definition.constraints is not None
    [requirement] = definition.constraints.requirements
    typed_name = requirement.typed_global_name
    assert typed_name.enclosing_fqun is definition.typed_name.name_content.fqun
    assert typed_name.full_typed_name == "action<my_mv:example.com:my_lib:/some/action>"
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=39
    )


def test_multiple_definitions_with_blocks(parse: Parse):
    program = parse(
        "define the potential position<standard:/first> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first_child>.\n"
        + "    }\n"
        + "}\n"
        + "define the potential position<standard:/second> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</second_child>.\n"
        + "    }\n"
        + "}\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.PositionDefinition)
    assert first.typed_name.full_typed_name == "position<standard:/first>"
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )
    assert first.constraints is not None
    [first_requirement] = first.constraints.requirements
    assert (
        first_requirement.typed_global_name.full_typed_name
        == "position<standard:/first_child>"
    )
    assert first_requirement.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=42
    )
    assert isinstance(second, ast.PositionDefinition)
    assert second.typed_name.full_typed_name == "position<standard:/second>"
    assert second.location == ast.SourceLocation(
        line=6, column=1, end_line=10, end_column=1
    )
    assert second.constraints is not None
    [second_requirement] = second.constraints.requirements
    assert (
        second_requirement.typed_global_name.full_typed_name
        == "position<standard:/second_child>"
    )
    assert second_requirement.location == ast.SourceLocation(
        line=8, column=9, end_line=8, end_column=43
    )
    assert program.location == ast.SourceLocation(
        line=1, column=1, end_line=10, end_column=1
    )


def test_mixed_block_and_terminator(parse: Parse):
    program = parse(
        "define the potential position<standard:/first>.\n"
        + "define the potential position<standard:/second> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action</do_work>.\n"
        + "    }\n"
        + "}\n"
    )
    [first, second] = program.definitions
    assert isinstance(first, ast.PositionDefinition)
    assert first.typed_name.full_typed_name == "position<standard:/first>"
    assert first.constraints is None
    assert first.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=47
    )
    assert isinstance(second, ast.PositionDefinition)
    assert second.typed_name.full_typed_name == "position<standard:/second>"
    assert second.location == ast.SourceLocation(
        line=2, column=1, end_line=6, end_column=1
    )
    assert second.constraints is not None
    [requirement] = second.constraints.requirements
    assert requirement.typed_global_name.full_typed_name == "action<standard:/do_work>"
    assert requirement.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )
    assert program.location == ast.SourceLocation(
        line=1, column=1, end_line=6, end_column=1
    )


def test_file_ending_after_block_open(parse: Parse):
    with pytest.raises(parser_exceptions.MissingPositionDefinitionContent) as exc_info:
        parse("define the potential position<standard:/path> {\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 48
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 48


def test_missing_newline_after_block_open(parse: Parse):
    with pytest.raises(parser_exceptions.EmptyBlock) as exc_info:
        parse("define the potential position<standard:/path> {}\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 48
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 48


def test_comment_directly_after_block_open(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingSpaceBeforeCommentAfterBrace
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {# note\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 65


def test_comment_directly_after_block_close(parse: Parse):
    with pytest.raises(
        parser_exceptions.MissingSpaceBeforeCommentAfterBrace
    ) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }# note\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 6


def test_no_space_before_brace(parse: Parse):
    with pytest.raises(parser_exceptions.MissingWhitespaceBeforeBrace) as exc_info:
        parse("define the potential position<standard:/path>{\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 46


def test_missing_terminator_still_works(parse: Parse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        parse("define the potential position<standard:/path>\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_column == 46


def test_missing_outer_block_close_with_inner_block_message(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseBrace) as exc_info:
        parse(
            "define the potential action<standard:/path> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 45


def test_position_constraint_invalid_type_keyword(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as exc_info:
        parse(
            "define the potential position<my_lib:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the osition<my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
            + "define the potential position<my_lib:/path>.\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 20
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 26


def test_position_constraint_missing_type_keyword(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedConstraintNameType) as exc_info:
        parse(
            "define the potential position<my_lib:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the <my_lib:/path>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 20
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 20


def test_whitespace_line_at_start_of_potential_position_definition_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    \n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_whitespace_line_after_position_constraint_block(parse: Parse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "    \n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 1


def test_whitespace_line_at_start_of_position_constraint_block(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        \n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 1


def test_whitespace_line_after_position_requirement_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "        \n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 1


def test_control_character_after_potential_position_definition_block_close(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "}\x01\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 2
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 2


def test_text_after_potential_literal_definition_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>.\n"
            + "}x\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 2
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 2


def test_text_after_operation_definition_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}x\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 2
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 2


def test_text_after_view_definition_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }x\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 7
    assert error.value.location.column == 6
    assert error.value.location.end_line == 7
    assert error.value.location.end_column == 6


def test_text_after_operation_statements_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }x\n"
            + "}\n"
        )
    assert error.value.location.line == 4
    assert error.value.location.column == 6
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 6


def test_text_after_operation_arguments_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterCloseBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at view<left>.\n"
            + "        }x\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 5
    assert error.value.location.column == 10
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 10


def test_text_after_operation_arguments_block_open(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterOpenBrace) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {x\n"
            + "            with view<a> looking at view<left>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.location.line == 3
    assert error.value.location.column == 40
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 40
