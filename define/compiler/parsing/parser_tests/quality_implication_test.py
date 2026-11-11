# pyright: reportUnusedCallResult=false
"""Quality Implication Statement parser tests.

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
    assert implication.location == rendering.SourceLocation(
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
    assert full_fqun.multiverse.location == rendering.SourceLocation(
        line=2, column=34, end_line=2, end_column=35
    )
    assert full_fqun.authority is not None
    assert full_fqun.authority.name == "example.com"
    assert full_fqun.authority.location == rendering.SourceLocation(
        line=2, column=37, end_line=2, end_column=47
    )
    assert full_fqun.universe.name == "my_lib"
    assert full_fqun.universe.location == rendering.SourceLocation(
        line=2, column=49, end_line=2, end_column=54
    )
    assert full_fqun.location == rendering.SourceLocation(
        line=2, column=34, end_line=2, end_column=54
    )
    assert full_name.name_content.path.name == "/full"
    short_multiverse_name = short_multiverse.typed_global_name
    short_multiverse_fqun = short_multiverse_name.name_content.fqun
    assert short_multiverse_fqun is not None
    assert short_multiverse_fqun.multiverse is None
    assert short_multiverse_fqun.authority is not None
    assert short_multiverse_fqun.authority.name == "example.com"
    assert short_multiverse_fqun.authority.location == rendering.SourceLocation(
        line=3, column=34, end_line=3, end_column=44
    )
    assert short_multiverse_fqun.universe.name == "my_lib"
    assert short_multiverse_fqun.universe.location == rendering.SourceLocation(
        line=3, column=46, end_line=3, end_column=51
    )
    assert short_multiverse_fqun.location == rendering.SourceLocation(
        line=3, column=34, end_line=3, end_column=51
    )
    assert short_multiverse_name.name_content.path.name == "/short_mv"
    universe_only_name = universe_only.typed_global_name
    universe_only_fqun = universe_only_name.name_content.fqun
    assert universe_only_fqun is not None
    assert universe_only_fqun.multiverse is None
    assert universe_only_fqun.authority is None
    assert universe_only_fqun.universe.name == "standard"
    assert universe_only_fqun.universe.location == rendering.SourceLocation(
        line=4, column=34, end_line=4, end_column=41
    )
    assert universe_only_fqun.location == rendering.SourceLocation(
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
    assert implication.location == rendering.SourceLocation(
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
    assert implication.location == rendering.SourceLocation(
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
    assert first.location == rendering.SourceLocation(
        line=2, column=5, end_line=2, end_column=41
    )
    second_name = second.typed_global_name
    assert second_name.name_content.path.name == "/second"
    assert second.location == rendering.SourceLocation(
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
    assert first.location == rendering.SourceLocation(
        line=3, column=5, end_line=3, end_column=41
    )
    second_name = second.typed_global_name
    assert second_name.name_content.path.name == "/second"
    assert second.location == rendering.SourceLocation(
        line=6, column=5, end_line=6, end_column=40
    )


# --- Statement-level syntax errors ---


def test_implication_missing_open_angle_at_eol(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenAngleBracket)
    assert error.location.line == 2
    assert error.location.column == 33
    assert error.location.end_line == 2
    assert error.location.end_column == 33


def test_implication_missing_open_angle_with_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenAngleBracket)
    assert error.location.line == 2
    assert error.location.column == 33
    assert error.location.end_line == 2
    assert error.location.end_column == 33


def test_implication_missing_open_angle_with_trailing_space(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position .\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingOpenAngleBracket)
    assert error.location.line == 2
    assert error.location.column == 33
    assert error.location.end_line == 2
    assert error.location.end_column == 33


def test_implication_empty_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position<>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.EmptyName)
    assert error.location.line == 2
    assert error.location.column == 34
    assert error.location.end_line == 2
    assert error.location.end_column == 34


def test_implication_newline_inside_name(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position<\n"
        + "        /required>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.EmptyName)
    assert error.location.line == 2
    assert error.location.column == 34
    assert error.location.end_line == 2
    assert error.location.end_column == 34


def test_implication_missing_close_angle(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseAngleBracket)
    assert error.location.line == 2
    assert error.location.column == 44
    assert error.location.end_line == 2
    assert error.location.end_column == 44


def test_implication_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.syntax_error is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=44, end_line=2, end_column=44
            )
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [implication] = definition.quality_implications
    assert implication.typed_global_name.name_content.path.name == "/required"
    assert implication.location == rendering.SourceLocation(
        line=2, column=5, end_line=2, end_column=43
    )


def test_implication_missing_newline_after_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.    it also assigns the position</other>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 2
    assert error.location.column == 45
    assert error.location.end_line == 2
    assert error.location.end_column == 45


def test_implication_missing_space_after_keyword(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns theposition</required>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingWhitespace)
    assert error.location.line == 2
    assert error.location.column == 24
    assert error.location.end_line == 2
    assert error.location.end_column == 31


def test_implication_extra_space_after_keyword(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the  position</required>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExtraWhitespace)
    assert error.location.line == 2
    assert error.location.column == 24
    assert error.location.end_line == 2
    assert error.location.end_column == 25


def test_implication_local_name_where_global_required(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position<foo>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidGlobalName)
    assert error.location.line == 2
    assert error.location.column == 34
    assert error.location.end_line == 2
    assert error.location.end_column == 36


def test_implication_chained_name_not_allowed(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</a>::position</b>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingTerminator)
    assert error.location.line == 2
    assert error.location.column == 37
    assert error.location.end_line == 2
    assert error.location.end_column == 37


# --- Block-level placement errors ---


def test_implication_after_quality_assignment_block_in_potential_position(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "    }\n"
        + "    it also assigns the position</required>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseBrace)
    assert error.location.line == 5
    assert error.location.column == 5
    assert error.location.end_line == 5
    assert error.location.end_column == 44


def test_implication_after_local_position_in_action_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it also assigns the position</required>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.QualityImplicationInWrongOrder)
    assert error.location.line == 3
    assert error.location.column == 5
    assert error.location.end_line == 3
    assert error.location.end_column == 23


def test_implication_after_trigger_conditions_block_in_action(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        it also assigns the position</required>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidActionStatementsBlock)
    assert error.location.line == 6
    assert error.location.column == 9
    assert error.location.end_line == 6
    assert error.location.end_column == 48


def test_implication_inside_quality_assignment_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</implied>.\n"
        + "        it also assigns the position</required>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidQualityAssignmentBlock)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 48


def test_implication_inside_action_statements_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "        it also assigns the position</required>.\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidActionStatementsBlock)
    assert error.location.line == 6
    assert error.location.column == 9
    assert error.location.end_line == 6
    assert error.location.end_column == 48


def test_implication_inside_trigger_conditions_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        it also assigns the position</required>.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.InvalidTriggerConditionsBlock)
    assert error.location.line == 4
    assert error.location.column == 9
    assert error.location.end_line == 4
    assert error.location.end_column == 48


def test_implication_inside_local_position_definition_quality_assignment_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
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
    assert isinstance(error, syntax_errors.InvalidQualityAssignmentBlock)
    assert error.location.line == 4
    assert error.location.column == 13
    assert error.location.end_line == 4
    assert error.location.end_column == 52


def test_implication_at_global_scope(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "it also assigns the position</required>.\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert isinstance(error, syntax_errors.ExpectedGlobalDefinition)
    assert error.location.line == 1
    assert error.location.column == 1
    assert error.location.end_line == 1
    assert error.location.end_column == 40


# --- Block content errors ---


def test_implication_only_in_action_definition_block(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the position</required>.\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingActionDefinitionSyntax)
    assert error.location.line == 3
    assert error.location.column == 1
    assert error.location.end_line == 3
    assert error.location.end_column == 1


def test_quality_implication_ends_after_keyword(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    it also assigns the\n"
        + "    define the position<run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.ExpectedPositionOrAction)
    assert error.location.line == 2
    assert error.location.column == 24
    assert error.location.end_line == 2
    assert error.location.end_column == 24
