# pyright: reportUnusedCallResult=false
"""Trigger condition statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast, name_types
from define.compiler.errors import diagnostics, syntax_errors

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
        ParseWithDiagnostics,
    )


def test_trigger_condition_with_local_position(parse: Parse):
    program = parse(
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
    assert condition.location == rendering.SourceLocation(
        line=4, column=9, end_line=4, end_column=44
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "my_pos"


def test_trigger_condition_with_comments(parse: Parse):
    program = parse(
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
    assert condition.location == rendering.SourceLocation(
        line=5, column=9, end_line=5, end_column=41
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "run"


def test_trigger_condition_with_blank_lines(parse: Parse):
    program = parse(
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
    assert condition.location == rendering.SourceLocation(
        line=5, column=9, end_line=5, end_column=41
    )
    typed_name = condition.typed_name
    assert typed_name.name_type == name_types.NameType.POSITION
    assert typed_name.name_content.name == "run"


def test_chained_name_is_parse_error(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>::position</other> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ChainedNameInPositionPresenceStatement)
    assert error.location.line == 4
    assert error.location.column == 26
    assert error.location.end_line == 4
    assert error.location.end_column == 27


def test_global_name_is_parse_error(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "        the position</some_pos> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.GlobalNameWhereLocalNameExpected)
    assert error.location.line == 3
    assert error.location.column == 22
    assert error.location.end_line == 3
    assert error.location.end_column == 30


def test_trigger_block_same_line_no_space(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {} and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.EmptyBlock)
    assert error.location.line == 3
    assert error.location.column == 22
    assert error.location.end_line == 3
    assert error.location.end_column == 22


def test_trigger_block_same_line_with_space(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when { } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterOpenBrace)
    assert error.location.line == 3
    assert error.location.column == 22
    assert error.location.end_line == 3
    assert error.location.end_column == 22


def test_trigger_block_closing_brace_same_line(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {}\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.EmptyBlock)
    assert error.location.line == 3
    assert error.location.column == 22
    assert error.location.end_line == 3
    assert error.location.end_column == 22


def test_empty_trigger_block_is_error(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    it happens when {\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingTriggerConditionContent)
    assert error.location.line == 3
    assert error.location.column == 5
    assert error.location.end_line == 3
    assert error.location.end_column == 5


def test_invalid_content_in_trigger_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        nonsense\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidTriggerConditionsBlock)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 16


def test_trigger_condition_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=4, column=41, end_line=4, end_column=41
            )
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    condition = definition.trigger_conditions.condition
    assert isinstance(condition, ast.PositionPresenceStatement)
    assert condition.location == rendering.SourceLocation(
        line=4, column=9, end_line=4, end_column=40
    )


def test_missing_space_before_has_a_particle(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 4
    assert error.location.column == 26
    assert error.location.end_line == 4
    assert error.location.end_column == 28


def test_missing_has_a_particle(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run>.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidHasAParticleSyntax)
    assert error.location.line == 4
    assert error.location.column == 26
    assert error.location.end_line == 4
    assert error.location.end_column == 26


def test_comment_trailing_space_in_trigger_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        # comment \n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=4,
                column=18,
                end_line=4,
                end_column=18,
            )
        )
    ]


def test_comment_trailing_space_after_trigger_condition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "        # comment \n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=5,
                column=18,
                end_line=5,
                end_column=18,
            )
        )
    ]


def test_position_presence_ends_after_the(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the  \n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 4
    assert error.location.column == 12
    assert error.location.end_line == 4
    assert error.location.end_column == 12


def test_value_in_position_presence_statement(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the value<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 4
    assert error.location.column == 13
    assert error.location.end_line == 4
    assert error.location.end_column == 17


def test_no_space_after_the_in_position_presence(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        theposition<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 4
    assert error.location.column == 12
    assert error.location.end_line == 4
    assert error.location.end_column == 19


def test_source_ends_in_trigger_conditions_block(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseBrace)
    assert error.location.line == 3
    assert error.location.column == 5
    assert error.location.end_line == 3
    assert error.location.end_column == 21


def test_invisible_character_in_position_presence_name_type(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/my_action> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the posi\u200btion<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvisibleCharacterError)
    assert error.char == "\u200b"
    assert error.location.line == 4
    assert error.location.column == 17
    assert error.location.end_line == 4
    assert error.location.end_column == 17
