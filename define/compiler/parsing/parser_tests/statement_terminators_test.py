# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler import ast
from define.compiler.errors import diagnostics, syntax_errors

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseSyntaxError,
        ParseWithDiagnostics,
    )


def test_valid_terminator(parse: Parse):
    program = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    [definition] = program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.location == rendering.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )
    assert definition.quality_assignment_block is None


def test_missing_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error("define the potential position<standard:/path>\n")
    assert isinstance(error, syntax_errors.MissingTerminatorOrBrace)
    assert error.location.line == 1
    assert error.location.end_line == 1
    assert error.location.column == 46
    assert error.location.end_column == 46


def test_missing_newline_after_terminator(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics("define the potential position<standard:/path>.")
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=47, end_line=1, end_column=47
            )
        ),
    ]


def test_missing_newline_after_last_definition(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/first>.\n"
        + "define the potential position<mv:define-lang.org:parser:/second>."
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=rendering.SourceLocation(
                line=2, column=66, end_line=2, end_column=66
            )
        ),
    ]


def test_missing_newline_between_global_definitions(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>.define the potential action<mv:define-lang.org:parser:/path>.\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 1
    assert error.location.column == 64
    assert error.location.end_line == 1
    assert error.location.end_column == 64


def test_double_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>..\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 1
    assert error.location.end_line == 1
    assert error.location.column == 64
    assert error.location.end_column == 64


def test_comment_directly_after_terminator(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>.# comment\n"
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=63, end_line=1, end_column=64
            )
        ),
    ]


def test_letter_after_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>.x\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 1
    assert error.location.column == 64
    assert error.location.end_line == 1
    assert error.location.end_column == 64


def test_spaces_and_letter_after_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>.  x\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 1
    assert error.location.column == 64
    assert error.location.end_line == 1
    assert error.location.end_column == 64


def test_non_ascii_character_after_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path>.é\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 1
    assert error.location.column == 64
    assert error.location.end_line == 1
    assert error.location.end_column == 64


def test_space_before_terminator(parse_syntax_error: ParseSyntaxError):
    error = parse_syntax_error(
        "define the potential position<mv:my.domain.com:my_lib:/some_name .\n"
    )
    assert isinstance(error, syntax_errors.MissingCloseAngleBracket)
    assert error.location.line == 1
    assert error.location.column == 67
    assert error.location.end_line == 1
    assert error.location.end_column == 67
    assert error.name == "mv:my.domain.com:my_lib:/some_name ."


def test_trailing_space_before_newline(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics("define the potential position<standard:/path>. \n")
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=1,
                column=47,
                end_line=1,
                end_column=47,
            )
        )
    ]


def test_several_trailing_spaces_before_newline(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>.   \n"
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=1,
                column=64,
                end_line=1,
                end_column=66,
            )
        )
    ]


def test_trailing_space_at_end_of_source(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>. "
    )
    assert result.syntax_error is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=64, end_line=1, end_column=64
            )
        ),
        diagnostics.MissingNewlineAtEndOfFileDiagnostic(
            location=rendering.SourceLocation(
                line=1, column=65, end_line=1, end_column=65
            )
        ),
    ]


def test_quality_assignment_without_terminator_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<my_lib:/hello/hello>.\n"
        + "define the potential position<my_lib:/sub/sub> {\n"
        + "    it may only contain particles where {\n"
        + "        it has the action<std:/path/sub>\n"
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
    [_, definition] = result.program.definitions
    assert isinstance(definition, ast.PositionDefinition)
    assert definition.quality_assignment_block is not None
    [quality_assignment] = definition.quality_assignment_block.statements
    assert quality_assignment.typed_global_name.name_content.path.name == "/path/sub"
    assert quality_assignment.location == rendering.SourceLocation(
        line=4, column=9, end_line=4, end_column=40
    )


def test_text_where_position_definition_terminator_belongs(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential position<mv:define-lang.org:parser:/path> x\n"
    )
    assert isinstance(error, syntax_errors.MissingTerminatorOrBrace)
    assert error.location.line == 1
    assert error.location.column == 63
    assert error.location.end_line == 1
    assert error.location.end_column == 63


def test_text_after_encoding_quality_assignment_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal>.x\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 2
    assert error.location.column == 35
    assert error.location.end_line == 2
    assert error.location.end_column == 35


def test_text_after_logical_operation_support_block_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential value<standard:/number/natural> {\n"
        + "    it supports the logical_operation<standard:/number/add> {\n"
        + "        it may be read.x\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 3
    assert error.location.column == 24
    assert error.location.end_line == 3
    assert error.location.end_column == 24


def test_text_after_value_setting_literal_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
        + "    it happens when {\n"
        + "        this particle is created.\n"
        + "    } and it does {\n"
        + '        set the value of position<dest> from literal</text>"a".x\n'
        + "    }\n}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 5
    assert error.location.column == 64
    assert error.location.end_line == 5
    assert error.location.end_column == 64


def test_text_after_operation_execution_terminator(
    parse_syntax_error: ParseSyntaxError,
):
    error = parse_syntax_error(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the operation</other>.x\n"
        + "    }\n"
        + "}\n"
    )
    assert isinstance(error, syntax_errors.MissingNewlineAfterTerminator)
    assert error.location.line == 3
    assert error.location.column == 39
    assert error.location.end_line == 3
    assert error.location.end_column == 39
