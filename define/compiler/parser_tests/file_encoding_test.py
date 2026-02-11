# pyright: reportUnusedCallResult=false
"""File encoding parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_bom_at_start(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        p.parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert exc_info.value.char == "\ufeff"
    assert exc_info.value.column == 1


def test_crlf_line_endings(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        p.parse("define the potential position<standard:/path>.\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.column == 47


def test_crlf_line_endings_in_comments(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        p.parse("# a comment\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.column == 12


def test_carriage_return_in_comment(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        p.parse("# comment with\rcarriage return\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.column == 15


def test_surrogate_character(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        p.parse("define the potential position<standard:/path>.\n\udcff\n")
    assert exc_info.value.char == "\udcff"
    assert exc_info.value.line == 2
    assert exc_info.value.column == 1
