# pyright: reportUnusedCallResult=false
"""Comment handling parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_comment_before_statement(p: parser.Parser) -> None:
    result = p.parse(
        "# This is a comment\ndefine the potential position<standard:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_comment_after_statement(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<standard:/path>.\n# Trailing comment\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_comment_on_same_line_as_statement(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>. # comment\n")
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_comment_on_same_line_multiple_spaces(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.   # comment\n")
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_multiline_comments_with_blank_hash_line(p: parser.Parser) -> None:
    result = p.parse(
        "# first line\n#\n# third line\ndefine the potential position<standard:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == ["standard:/path"]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_valid_syntax_in_comment_is_ignored(p: parser.Parser) -> None:
    result = p.parse(
        "# define the potential position<standard:/ignored>.\n"
        + "define the potential position<standard:/actual>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "standard:/actual"
    ]


def test_control_character_in_comment(p: parser.Parser) -> None:
    result = p.parse(
        "# comment with\x01control char\n"
        + "define the potential position<standard:/path>.\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ControlCharacterError)
    assert result.exception.line == 1
    assert result.exception.char == "\x01"
    assert result.exception.column == 15


def test_comment_with_trailing_whitespace(p: parser.Parser) -> None:
    result = p.parse("# comment with trailing space \n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert result.exception.line == 1
    assert result.exception.char == " "
    assert result.exception.column == 30


def test_same_line_comment_with_trailing_whitespace(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>. # comment \n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert result.exception.line == 1
    assert result.exception.char == " "
    assert result.exception.column == 57


def test_comment_only_file_without_newline(p: parser.Parser) -> None:
    result = p.parse("# a comment")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert str(result.exception.token) == ""
    assert result.exception.line == 1
    assert result.exception.column == 1


def test_empty_comment_hash_only_file_by_itself(p: parser.Parser) -> None:
    result = p.parse("#")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert str(result.exception.token) == ""
    assert result.exception.line == 1
    assert result.exception.column == 1


def test_empty_comment_hash_newline_file_by_itself(p: parser.Parser) -> None:
    result = p.parse("#\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ExpectedGlobalDefinition)
    assert str(result.exception.token) == ""
    assert result.exception.line == 1
    assert result.exception.column == 2


def test_empty_comment_hash_space_file_by_itself(p: parser.Parser) -> None:
    result = p.parse("# ")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.line == 1
    assert result.exception.column == 2


def test_empty_comment_hash_space_newline_file_by_itself(p: parser.Parser) -> None:
    result = p.parse("# \n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.line == 1
    assert result.exception.column == 2


def test_empty_comment_hash_newline_above_statement(p: parser.Parser) -> None:
    result = p.parse(
        "#\ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_empty_comment_hash_space_newline_above_statement(p: parser.Parser) -> None:
    result = p.parse(
        "# \ndefine the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.line == 1
    assert result.exception.column == 2


def test_empty_comment_hash_only_after_statement_same_line(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>. #"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.MissingNewlineAtEof)
    assert str(result.exception.token) == ""
    assert result.exception.line == 1
    assert result.exception.column == 63


def test_empty_comment_hash_newline_after_statement_same_line(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>. #\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
    assert get_tokens_by_type(result.tree, "COMMENT") == []


def test_empty_comment_hash_space_after_statement_same_line(p: parser.Parser) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>. # "
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.line == 1
    assert result.exception.column == 66


def test_empty_comment_hash_space_newline_after_statement_same_line(
    p: parser.Parser,
) -> None:
    result = p.parse(
        "define the potential position<mv:define-lang.org:parser:/path>. # \n"
    )
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.TrailingWhitespaceError)
    assert str(result.exception.char) == " "
    assert result.exception.line == 1
    assert result.exception.column == 66
