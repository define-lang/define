"""Trailing whitespace parser tests: each line that ends with spaces gets a diagnostic, and the parse goes on.

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


def test_spaces_after_terminator_do_not_stop_the_next_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>.  \n"
        + "define the potential position<mv:define-lang.org:parser:/second>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=65, end_line=1, end_column=66)
        )
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=65
    )


def test_spaces_after_block_open_do_not_stop_the_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> { \n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=65, end_line=1, end_column=65)
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


def test_spaces_after_block_close_do_not_stop_the_next_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }  \n"
        + "}  \n"
        + "define the potential position<mv:define-lang.org:parser:/second>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=4, column=6, end_line=4, end_column=7)
        ),
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=5, column=2, end_line=5, end_column=3)
        ),
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=6, column=1, end_line=6, end_column=65
    )


def test_line_of_only_spaces_in_a_block_gets_no_indentation_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "  \n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=3, column=1, end_line=3, end_column=2)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_content.path.name == "/child"
    assert quality_assignment.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )


def test_misindented_comment_with_trailing_spaces_gets_both_diagnostics(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "  # note  \n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=2, column=9, end_line=2, end_column=10)
        ),
        diagnostics.IncorrectIndentationDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=2),
            expected_indent=4,
            actual_indent=2,
        ),
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_content.path.name == "/child"
    assert quality_assignment.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )


def test_spaces_after_comment_after_statement_do_not_stop_the_next_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first>. # note \n"
        + "        it has the position</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=3, column=44, end_line=3, end_column=44)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [_, second] = definition.quality_assignment_block.statements
    assert second.typed_global_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=37
    )


def test_each_line_with_trailing_spaces_gets_its_own_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>. \n"
        + "   \n"
        + "# note \n"
        + "define the potential position<mv:define-lang.org:parser:/second>.\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=65, end_line=1, end_column=65)
        ),
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=2, column=1, end_line=2, end_column=3)
        ),
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=3, column=7, end_line=3, end_column=7)
        ),
    ]
    assert result.program is not None
    [_, second] = result.program.definitions
    assert second.typed_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=4, column=1, end_line=4, end_column=65
    )


def test_trailing_spaces_before_a_syntax_error_are_reported_with_it(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>. \n"
        + "define the potential position<mv:define-lang.org:parser:/second>\n"
    )
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=65, end_line=1, end_column=65)
        )
    ]
    assert isinstance(result.exception, parser_exceptions.MissingTerminatorOrBrace)
    assert result.exception.location == ast.SourceLocation(
        line=2, column=65, end_line=2, end_column=65
    )
    assert result.program is None
