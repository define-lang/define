"""Multiverse name format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_uppercase_in_multiverse(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<MyMv:example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["MyMv"]


def test_multiverse_starting_with_underscore(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<_mymv:example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["_mymv"]


def test_multiverse_ending_with_underscore(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv_:example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["mymv_"]


def test_single_char_multiverse(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<x:example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["x"]


def test_non_ascii_in_multiverse(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<m\u00fcv:example.com:my_lib:/path>.\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["m\u00fcv"]
