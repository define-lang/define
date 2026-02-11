# pyright: reportUnusedCallResult=false
"""Incomplete statement parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_empty_file(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyFileError) as exc_info:
        p.parse("")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.column == 1


def test_file_all_spaces(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        p.parse("   ")
    assert exc_info.value.char == " "
    assert exc_info.value.column == 1


def test_file_spaces_and_newlines_only(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        p.parse(" \n  \n ")
    assert exc_info.value.char == " "
    assert exc_info.value.column == 1


def test_file_all_newlines(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyFileError) as exc_info:
        p.parse("\n\n\n")
    assert str(exc_info.value.token) == ""
    assert exc_info.value.column == 1


def test_extra_space_after_define(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
        p.parse("define  the potential position<standard:/path>.\n")
    assert exc_info.value.column == 1


def test_extra_space_after_the(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
        p.parse("define the  potential position<standard:/path>.\n")
    assert exc_info.value.column == 1


def test_extra_space_after_potential(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
        p.parse("define the potential  position<standard:/path>.\n")
    assert exc_info.value.column == 1


def test_extra_space_after_potential_action(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UnexpectedWhitespaceError) as exc_info:
        p.parse("define the potential  action<standard:/path>.\n")
    assert exc_info.value.column == 1


def test_define_the_potential_no_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
        p.parse("define the potential\n")
    assert str(exc_info.value.token) == "define"
    assert exc_info.value.column == 1


def test_define_the_potential_with_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
        p.parse("define the potential.\n")
    assert str(exc_info.value.token) == "define"
    assert exc_info.value.column == 1


def test_define_the_no_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
        p.parse("define the\n")
    assert str(exc_info.value.token) == "define"
    assert exc_info.value.column == 1


def test_define_the_with_terminator(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.IncompleteStatementError) as exc_info:
        p.parse("define the.\n")
    assert str(exc_info.value.token) == "define"
    assert exc_info.value.column == 1
