# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_missing_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingTerminatorError) as exc_info:
        p.parse("define the potential position<standard:/path>\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.column == 46


def test_missing_newline_after_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingNewlineError) as exc_info:
        p.parse("define the potential position<standard:/path>.")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.column == 46


def test_trailing_space_before_newline(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        p.parse("define the potential position<standard:/path>. \n")
    assert exc_info.value.char == " "
    assert exc_info.value.column == 47
