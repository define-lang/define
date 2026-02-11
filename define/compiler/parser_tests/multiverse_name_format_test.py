# pyright: reportUnusedCallResult=false
"""Multiverse name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_uppercase_in_multiverse(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
        p.parse("define the potential position<MyMv:example.com:my_lib:/path>.\n")
    assert exc_info.value.char == "M"
    assert exc_info.value.column == 31


def test_multiverse_starting_with_underscore(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
        p.parse("define the potential position<_mymv:example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "_mymv"
    assert exc_info.value.column == 31


def test_multiverse_ending_with_underscore(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
        p.parse("define the potential position<mymv_:example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "mymv_"
    assert exc_info.value.column == 31


def test_single_char_multiverse(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
        p.parse("define the potential position<x:example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "x"
    assert exc_info.value.column == 31


def test_non_ascii_in_multiverse(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidMultiverseError) as exc_info:
        p.parse("define the potential position<m\u00fcv:example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "m"
    assert exc_info.value.column == 31
