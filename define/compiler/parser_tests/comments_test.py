# pyright: reportUnusedCallResult=false
"""Comment handling parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.conftest import Parse
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_comment_before_statement(parse: Parse) -> None:
    tree = parse(
        "# This is a comment\ndefine the potential position<standard:/path>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_comment_after_statement(parse: Parse) -> None:
    tree = parse("define the potential position<standard:/path>.\n# Trailing comment\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_comment_on_same_line_as_statement(parse: Parse) -> None:
    tree = parse("define the potential position<standard:/path>. # comment\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_comment_on_same_line_multiple_spaces(parse: Parse) -> None:
    tree = parse("define the potential position<standard:/path>.   # comment\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_multiline_comments_with_blank_hash_line(parse: Parse) -> None:
    tree = parse(
        "# first line\n#\n# third line\ndefine the potential position<standard:/path>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_valid_syntax_in_comment_is_ignored(parse: Parse) -> None:
    tree = parse(
        "# define the potential position<standard:/ignored>.\n"
        + "define the potential position<standard:/actual>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == ["standard:/actual"]


def test_control_character_in_comment(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "# comment with\x01control char\n"
            + "define the potential position<standard:/path>.\n"
        )
    assert exc_info.value.line == 1
    assert exc_info.value.char == "\x01"
    assert exc_info.value.column == 15


def test_control_character_in_inline_comment(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>. # comment\x00\n")
    assert exc_info.value.line == 1
    assert exc_info.value.char == "\x00"
    assert exc_info.value.column == 57


def test_comment_with_trailing_whitespace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("# comment with trailing space \n")
    assert exc_info.value.line == 1
    assert exc_info.value.char == " "
    assert exc_info.value.column == 30


def test_same_line_comment_with_trailing_whitespace(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("define the potential position<standard:/path>. # comment \n")
    assert exc_info.value.line == 1
    assert exc_info.value.char == " "
    assert exc_info.value.column == 57


def test_comment_only_file_without_newline(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("# a comment")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_empty_comment_hash_only_file_by_itself(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("#")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_empty_comment_hash_newline_file_by_itself(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("#\n")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 2


def test_empty_comment_hash_space_file_by_itself(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("# ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 2


def test_empty_comment_hash_space_newline_file_by_itself(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("# \n")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 2


def test_empty_comment_hash_newline_above_statement(parse: Parse) -> None:
    tree = parse("#\ndefine the potential position<mv:define-lang.org:parser:/path>.\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_empty_comment_hash_space_newline_above_statement(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("# \ndefine the potential position<mv:define-lang.org:parser:/path>.\n")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 2


def test_empty_comment_hash_only_after_statement_same_line(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>. #")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.line == 1
    assert exc_info.value.column == 63


def test_empty_comment_hash_newline_after_statement_same_line(parse: Parse) -> None:
    tree = parse("define the potential position<mv:define-lang.org:parser:/path>. #\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(tree, "COMMENT") == []


def test_empty_comment_hash_space_after_statement_same_line(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>. # ")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 66


def test_empty_comment_hash_space_newline_after_statement_same_line(
    parse: Parse,
) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/path>. # \n")
    assert str(exc_info.value.char) == " "
    assert exc_info.value.line == 1
    assert exc_info.value.column == 66
