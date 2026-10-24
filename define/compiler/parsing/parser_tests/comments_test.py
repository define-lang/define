# pyright: reportUnusedCallResult=false
"""Comment handling parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


def test_comment_before_statement(parse: Parse):
    program = parse(
        "# This is a comment\ndefine the potential position<standard:/path>.\n"
    )
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=46
    )
    assert program.location == definition.location


def test_comment_after_statement(parse: Parse):
    program = parse(
        "define the potential position<standard:/path>.\n# Trailing comment\n"
    )
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=46
    )
    assert program.location == definition.location


def test_comment_on_same_line_as_statement(parse: Parse):
    program = parse("define the potential position<standard:/path>. # comment\n")
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=46
    )
    assert program.location == definition.location


def test_comment_on_same_line_multiple_spaces(parse: Parse):
    program = parse("define the potential position<standard:/path>.   # comment\n")
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=46
    )
    assert program.location == definition.location


def test_multiline_comments_with_blank_hash_line(parse: Parse):
    program = parse(
        "# first line\n#\n# third line\ndefine the potential position<standard:/path>.\n"
    )
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=4, column=1, end_line=4, end_column=46
    )
    assert program.location == definition.location


def test_valid_syntax_in_comment_is_ignored(parse: Parse):
    program = parse(
        "# define the potential position<standard:/ignored>.\n"
        + "define the potential position<standard:/actual>.\n"
    )
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/actual>"
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=48
    )


def test_non_ascii_comment(parse: Parse):
    program = parse(
        "# café comment\ndefine the potential position<standard:/path>. # naïve\n"
    )
    [definition] = program.definitions
    assert definition.typed_name.full_typed_name == "position<standard:/path>"
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=46
    )
    assert program.location == definition.location


def test_non_ascii_comment_with_trailing_whitespace(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<standard:/path>. # café \n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=54,
                end_line=1,
                end_column=54,
            )
        )
    ]


def test_control_character_in_comment(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "# comment with\x01control char\n"
            + "define the potential position<standard:/path>.\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 15


def test_control_character_in_inline_comment(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>. # comment\x00\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == "\x00"
    assert exc_info.value.location.column == 57
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 57


def test_comment_with_trailing_whitespace(parse_with_diagnostics: ParseWithDiagnostics):
    result = parse_with_diagnostics("# comment with trailing space \n")
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=30, end_line=1, end_column=30)
        ),
    ]
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=1
    )


def test_same_line_comment_with_trailing_whitespace(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<standard:/path>. # comment \n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=57,
                end_line=1,
                end_column=57,
            )
        )
    ]


def test_comment_only_file_without_newline(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("# a comment")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_only_file_by_itself(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("#")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_newline_file_by_itself(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("#\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_space_file_by_itself(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics("# ")
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=2, end_line=1, end_column=2)
        ),
    ]
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=1
    )


def test_empty_comment_hash_space_newline_file_by_itself(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics("# \n")
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=2, end_line=1, end_column=2)
        ),
    ]
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=1
    )


def test_empty_comment_hash_newline_above_statement(parse: Parse):
    program = parse(
        "#\ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=63
    )
    assert program.location == definition.location


def test_empty_comment_hash_space_newline_above_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# \ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=2,
                end_line=1,
                end_column=2,
            )
        )
    ]


def test_empty_comment_hash_only_after_statement_same_line(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>. #")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_column == 66


def test_empty_comment_hash_newline_after_statement_same_line(
    parse: Parse,
):
    program = parse(
        "define the potential position<mv:define-lang.org:parser:/path>. #\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=1, column=1, end_line=1, end_column=63
    )
    assert program.location == definition.location


def test_empty_comment_hash_space_after_statement_same_line(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>. # "
    )
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(line=1, column=66, end_line=1, end_column=66)
        ),
    ]
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAtEof)
    assert result.exception.location == ast.SourceLocation(
        line=1, column=67, end_line=1, end_column=67
    )


def test_empty_comment_hash_space_newline_after_statement_same_line(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential position<mv:define-lang.org:parser:/path>. # \n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=1,
                column=66,
                end_line=1,
                end_column=66,
            )
        )
    ]


def test_comment_with_trailing_whitespace_before_encoding_quality_assignment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    # note \n"
        + "    it has the encoding</decimal>.\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=2,
                column=11,
                end_line=2,
                end_column=11,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_encoding_quality_assignment(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
        + "    it has the encoding</decimal>.\n"
        + "    # note \n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=11,
                end_line=3,
                end_column=11,
            )
        )
    ]


def test_comment_with_carriage_return_after_encoding_quality_assignment(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encoding</decimal>.\n"
            + "    # note\r\n"
            + "}\n"
        )
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 11
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 11


def test_comment_with_trailing_whitespace_before_operation_statements_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    # note \n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=2,
                column=11,
                end_line=2,
                end_column=11,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_operation_statements_block(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "    # note \n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=5,
                column=11,
                end_line=5,
                end_column=11,
            )
        )
    ]


def test_comment_with_trailing_whitespace_before_operation_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        # note \n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=15,
                end_line=3,
                end_column=15,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_operation_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "        # note \n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=4,
                column=15,
                end_line=4,
                end_column=15,
            )
        )
    ]


def test_comment_with_trailing_whitespace_before_operation_argument(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the operation</other> {\n"
        + "            # note \n"
        + "            with view<a> looking at view<left>.\n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=4,
                column=19,
                end_line=4,
                end_column=19,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_operation_argument(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    it does {\n"
        + "        execute the operation</other> {\n"
        + "            with view<a> looking at view<left>.\n"
        + "            # note \n"
        + "        }\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=5,
                column=19,
                end_line=5,
                end_column=19,
            )
        )
    ]


def test_comment_with_trailing_whitespace_before_view_direction_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        # note \n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=15,
                end_line=3,
                end_column=15,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_view_read_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        # note \n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=4,
                column=15,
                end_line=4,
                end_column=15,
            )
        )
    ]


def test_comment_with_trailing_whitespace_after_view_written_statement(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it is written.\n"
        + "        # note \n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=5,
                column=15,
                end_line=5,
                end_column=15,
            )
        )
    ]


def test_comment_with_trailing_whitespace_before_view_close(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "define the operation<mv:define-lang.org:parser:/add> {\n"
        + "    define the view<left> {\n"
        + "        it is read.\n"
        + "        it may only contain particles where {\n"
        + "            it has the value</number>.\n"
        + "        }\n"
        + "        # note \n"
        + "    }\n"
        + "    it does {\n"
        + "        execute the encoding operation.\n"
        + "    }\n"
        + "}\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.TrailingWhitespaceDiagnostic(
            location=ast.SourceLocation(
                line=7,
                column=15,
                end_line=7,
                end_column=15,
            )
        )
    ]
