# pyright: reportUnusedCallResult=false
"""File encoding parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parser_tests.conftest import Parse


def test_bom_at_start(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert exc_info.value.char == "\ufeff"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 1


def test_crlf_line_endings(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("define the potential position<standard:/path>.\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 47


def test_crlf_line_endings_in_comments(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("# a comment\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 12


def test_carriage_return_in_comment(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("# comment with\rcarriage return\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.line == 1
    assert exc_info.value.column == 15


def test_surrogate_character(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\udcff\n")
    assert exc_info.value.char == "\udcff"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_surrogate_range_start_boundary(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\ud800\n")
    assert exc_info.value.char == "\ud800"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_surrogate_range_end_boundary(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\udfff\n")
    assert exc_info.value.char == "\udfff"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_del_character(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\n\x7f\n")
    assert exc_info.value.char == "\x7f"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_invalid_character_error(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\n☃\n")
    assert exc_info.value.char == "☃"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_first_non_ascii_byte(parse: Parse) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\n\x80\n")
    assert exc_info.value.char == "\x80"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1


def test_comment_with_zero_width_joiner_in_grapheme_cluster(parse: Parse) -> None:
    tree = parse(
        "# devanagari ligature with ZWJ: \u0915\u094d\u200d\u0937\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]


def test_comment_with_valid_bidi_isolates(parse: Parse) -> None:
    tree = parse(
        "# isolate-wrapped rtl text: \u2067\u05e9\u05dc\u05d5\u05dd\u2069\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]
