"""Whitespace mistake parser tests: each mistake gets a diagnostic, and the parse goes on.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        ParseWithDiagnostics,
    )


def test_comment_without_space_after_terminator_does_not_stop_the_next_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>.# note\n"
        + "define the potential position<mv:define-lang.org:parser:/second>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic(
            location=ast.SourceLocation(line=1, column=64, end_line=1, end_column=65)
        )
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=65
    )


def test_comment_without_space_after_block_open_does_not_stop_the_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {# note\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingSpaceBeforeCommentAfterBraceDiagnostic(
            location=ast.SourceLocation(line=1, column=64, end_line=1, end_column=65)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_content.path.name == "/child"
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=36
    )


def test_comment_without_space_after_block_close_does_not_stop_the_next_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}# note\n"
        + "define the potential position<mv:define-lang.org:parser:/second>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingSpaceBeforeCommentAfterBraceDiagnostic(
            location=ast.SourceLocation(line=5, column=1, end_line=5, end_column=2)
        )
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=6, column=1, end_line=6, end_column=65
    )


def test_spaces_before_angle_bracket_in_reference_keep_the_reference(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position  </child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.SpaceBeforeOpenAngleBracketDiagnostic(
            location=ast.SourceLocation(line=3, column=28, end_line=3, end_column=29)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    typed_name = quality_assignment.typed_global_name
    assert typed_name.name_content.path.name == "/child"
    assert typed_name.location == ast.SourceLocation(
        line=3, column=20, end_line=3, end_column=37
    )


def test_space_before_angle_bracket_in_global_definition_keeps_the_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position <mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.SpaceBeforeOpenAngleBracketDiagnostic(
            location=ast.SourceLocation(line=1, column=30, end_line=1, end_column=30)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert definition.typed_name.name_content.path.name == "/path"
    assert definition.typed_name.location == ast.SourceLocation(
        line=1, column=22, end_line=1, end_column=63
    )


def test_space_before_angle_bracket_in_local_definition_keeps_the_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential action<mv:define-lang.org:parser:/act> {\n"
        + "    define the position <run>.\n"
        + "    it happens when {\n"
        + "        the position<run> has a particle.\n"
        + "    } and it does {\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.SpaceBeforeOpenAngleBracketDiagnostic(
            location=ast.SourceLocation(line=2, column=24, end_line=2, end_column=24)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.ActionDefinition)
    [interface_position] = definition.interface_positions
    assert interface_position.typed_name.name_content.name == "run"
    assert interface_position.typed_name.location == ast.SourceLocation(
        line=2, column=16, end_line=2, end_column=29
    )


def test_missing_newline_at_end_of_file_after_block_keeps_the_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=ast.SourceLocation(line=5, column=2, end_line=5, end_column=2)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=5, end_column=1
    )


def test_each_whitespace_mistake_gets_its_own_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position <mv:define-lang.org:parser:/first>.# note\n"
        + "define the potential position<mv:define-lang.org:parser:/second>."
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.SpaceBeforeOpenAngleBracketDiagnostic(
            location=ast.SourceLocation(line=1, column=30, end_line=1, end_column=30)
        ),
        diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic(
            location=ast.SourceLocation(line=1, column=65, end_line=1, end_column=66)
        ),
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=ast.SourceLocation(line=2, column=66, end_line=2, end_column=66)
        ),
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=65
    )


def test_whitespace_mistake_before_a_syntax_error_is_reported_with_it(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>.# note\n"
        + "define the potential position<mv:define-lang.org:parser:/second>\n"
    )
    assert result.diagnostics == [
        diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic(
            location=ast.SourceLocation(line=1, column=64, end_line=1, end_column=65)
        )
    ]
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert result.exception.location == ast.SourceLocation(
        line=2, column=65, end_line=2, end_column=65
    )
    assert result.program is None
