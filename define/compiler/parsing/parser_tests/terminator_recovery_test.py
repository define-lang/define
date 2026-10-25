"""Missing terminator parser tests: a statement whose line ends where its '.' belongs gets a diagnostic, and the parse goes on.

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


def test_missing_terminator_does_not_stop_the_next_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first>\n"
        + "        it has the position</second>.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
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


def test_each_missing_terminator_gets_its_own_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</first>\n"
        + "        it has the position</second>\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
        ),
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=4, column=37, end_line=4, end_column=37)
        ),
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [_, second] = definition.quality_assignment_block.statements
    assert second.typed_global_name.name_content.path.name == "/second"
    assert second.location == ast.SourceLocation(
        line=4, column=9, end_line=4, end_column=36
    )


def test_missing_terminator_before_trailing_spaces_gets_both_diagnostics(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child>  \n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=37)
        ),
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
        ),
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )


def test_missing_terminator_before_comment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child> # note\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )


def test_missing_terminator_before_comment_without_space(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child># note\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )


def test_missing_terminator_before_comment_that_is_not_ascii(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child> # café\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=3, column=36, end_line=3, end_column=36)
        )
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.location == ast.SourceLocation(
        line=3, column=9, end_line=3, end_column=35
    )


def test_missing_terminator_at_end_of_file(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics("define the encoding<standard:/number/natural>")
    assert result.exception is None
    assert result.diagnostics == [
        diagnostics.MissingTerminatorAtEndOfLineDiagnostic(
            location=ast.SourceLocation(line=1, column=46, end_line=1, end_column=46)
        ),
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=ast.SourceLocation(line=1, column=46, end_line=1, end_column=46)
        ),
    ]
    assert result.program is not None
    [definition] = result.program.definitions
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=45
    )


def test_text_after_statement_where_terminator_belongs_stops_the_parse(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child> and more\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingTerminator)
    assert result.exception.location == ast.SourceLocation(
        line=3, column=36, end_line=3, end_column=36
    )
    assert result.program is None


def test_carriage_return_in_comment_after_missing_terminator_stops_the_parse(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the position</child> # note\r\n"
        + "    }\n"
        + "}\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.char == "\r"
    assert result.exception.location == ast.SourceLocation(
        line=3, column=43, end_line=3, end_column=43
    )
    assert result.program is None
