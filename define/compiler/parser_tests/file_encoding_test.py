# pyright: reportUnusedCallResult=false
"""File encoding parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_bom_at_start(p: parser.Parser) -> None:
    result = p.parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.ByteOrderMarkError)
    assert result.exception.char == "\ufeff"
    assert result.exception.column == 1


def test_crlf_line_endings(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.\r\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.char == "\r"
    assert result.exception.column == 47


def test_crlf_line_endings_in_comments(p: parser.Parser) -> None:
    result = p.parse("# a comment\r\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.char == "\r"
    assert result.exception.column == 12


def test_carriage_return_in_comment(p: parser.Parser) -> None:
    result = p.parse("# comment with\rcarriage return\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.CarriageReturnError)
    assert result.exception.char == "\r"
    assert result.exception.column == 15


def test_surrogate_character(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.\n\udcff\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.exception.char == "\udcff"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_invalid_character_error(p: parser.Parser) -> None:
    result = p.parse("define the potential position<standard:/path>.\n☃\n")
    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidCharacterError)
    assert result.exception.char == "☃"
    assert result.exception.line == 2
    assert result.exception.column == 1


def test_comment_with_zero_width_joiner_in_grapheme_cluster(p: parser.Parser) -> None:
    result = p.parse(
        "# devanagari ligature with ZWJ: \u0915\u094d\u200d\u0937\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]


def test_comment_with_valid_bidi_isolates(p: parser.Parser) -> None:
    result = p.parse(
        "# isolate-wrapped rtl text: \u2067\u05e9\u05dc\u05d5\u05dd\u2069\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.diagnostics == []
    assert result.tree is not None
    assert get_tokens_by_type(result.tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
