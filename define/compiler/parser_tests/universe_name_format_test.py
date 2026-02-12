"""Universe name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_universe_with_uppercase(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:MyLib:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["MyLib"]


def test_universe_starting_with_underscore(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:_mylib:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["_mylib"]


def test_universe_ending_with_underscore(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:mylib_:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["mylib_"]


def test_single_char_universe(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:x:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["x"]


def test_non_ascii_in_universe(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:m\u00fclib:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["m\u00fclib"]


def test_universe_starting_with_underscore_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:example.com:_my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["_my_lib"]


def test_universe_ending_with_underscore_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:example.com:my_lib_:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib_"]


def test_single_char_universe_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:example.com:x:/path>.\n")
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["x"]
