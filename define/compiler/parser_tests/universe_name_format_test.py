# pyright: reportUnusedCallResult=false
"""Universe name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_universe_with_uppercase(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:MyLib:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["MyLib"]


def test_universe_starting_with_underscore(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<example.com:_mylib:/path>.\n")
    assert str(exc_info.value.token) == "_mylib"
    assert exc_info.value.column == 43


def test_universe_ending_with_underscore(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<example.com:mylib_:/path>.\n")
    assert str(exc_info.value.token) == "mylib_"
    assert exc_info.value.column == 43


def test_single_char_universe(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<example.com:x:/path>.\n")
    assert str(exc_info.value.token) == "x"
    assert exc_info.value.column == 43


def test_non_ascii_in_universe(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<example.com:m\u00fclib:/path>.\n")
    assert str(exc_info.value.token) == "m"
    assert exc_info.value.column == 43


def test_universe_starting_with_underscore_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<mymv:example.com:_my_lib:/path>.\n")
    assert str(exc_info.value.token) == "_my_lib"
    assert exc_info.value.column == 48


def test_universe_ending_with_underscore_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<mymv:example.com:my_lib_:/path>.\n")
    assert str(exc_info.value.token) == "my_lib_"
    assert exc_info.value.column == 48


def test_single_char_universe_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidUniverseError) as exc_info:
        p.parse("define the potential position<mymv:example.com:x:/path>.\n")
    assert str(exc_info.value.token) == "x"
    assert exc_info.value.column == 48
