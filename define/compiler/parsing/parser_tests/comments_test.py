# pyright: reportUnusedCallResult=false
"""Comment handling parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import global_typed_names

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_comment_before_statement(native_parse: NativeParse):
    program = native_parse(
        "# This is a comment\ndefine the potential position<standard:/path>.\n"
    )
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_comment_after_statement(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<standard:/path>.\n# Trailing comment\n"
    )
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_comment_on_same_line_as_statement(native_parse: NativeParse):
    program = native_parse("define the potential position<standard:/path>. # comment\n")
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_comment_on_same_line_multiple_spaces(native_parse: NativeParse):
    program = native_parse(
        "define the potential position<standard:/path>.   # comment\n"
    )
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_multiline_comments_with_blank_hash_line(native_parse: NativeParse):
    program = native_parse(
        "# first line\n#\n# third line\ndefine the potential position<standard:/path>.\n"
    )
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_valid_syntax_in_comment_is_ignored(native_parse: NativeParse):
    program = native_parse(
        "# define the potential position<standard:/ignored>.\n"
        + "define the potential position<standard:/actual>.\n"
    )
    assert global_typed_names(program) == ["position<standard:/actual>"]


def test_non_ascii_comment(native_parse: NativeParse):
    program = native_parse(
        "# café comment\ndefine the potential position<standard:/path>. # naïve\n"
    )
    assert global_typed_names(program) == ["position<standard:/path>"]


def test_non_ascii_comment_with_trailing_whitespace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse("define the potential position<standard:/path>. # café \n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == " "
    assert exc_info.value.location.column == 54
    assert exc_info.value.location.end_column == 54


def test_control_character_in_comment(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "# comment with\x01control char\n"
            + "define the potential position<standard:/path>.\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_column == 15


def test_control_character_in_inline_comment(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>. # comment\x00\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == "\x00"
    assert exc_info.value.location.column == 57
    assert exc_info.value.location.end_column == 57


def test_comment_with_trailing_whitespace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse("# comment with trailing space \n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == " "
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_column == 30


def test_same_line_comment_with_trailing_whitespace(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse("define the potential position<standard:/path>. # comment \n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.char == " "
    assert exc_info.value.location.column == 57
    assert exc_info.value.location.end_column == 57


def test_comment_only_file_without_newline(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("# a comment")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_only_file_by_itself(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("#")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_newline_file_by_itself(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("#\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_column == 1


def test_empty_comment_hash_space_file_by_itself(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse("# ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 2
    assert exc_info.value.location.end_column == 2


def test_empty_comment_hash_space_newline_file_by_itself(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse("# \n")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 2
    assert exc_info.value.location.end_column == 2


def test_empty_comment_hash_newline_above_statement(native_parse: NativeParse):
    program = native_parse(
        "#\ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert global_typed_names(program) == ["position<mv:define-lang.org:parser:/path>"]


def test_empty_comment_hash_space_newline_above_statement(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "# \ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 2
    assert exc_info.value.location.end_column == 2


def test_empty_comment_hash_only_after_statement_same_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>. #"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_column == 66


def test_empty_comment_hash_newline_after_statement_same_line(
    native_parse: NativeParse,
):
    program = native_parse(
        "define the potential position<mv:define-lang.org:parser:/path>. #\n"
    )
    assert global_typed_names(program) == ["position<mv:define-lang.org:parser:/path>"]


def test_empty_comment_hash_space_after_statement_same_line(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>. # "
        )
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_column == 66


def test_empty_comment_hash_space_newline_after_statement_same_line(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>. # \n"
        )
    assert str(exc_info.value.char) == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_column == 66
