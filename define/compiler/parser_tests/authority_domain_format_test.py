"""Authority domain format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from define.compiler import parser
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_authority_domain_with_dots_and_hyphens(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<my-host.example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["my-host.example.com"]


def test_authority_domain_without_dot(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<localhost:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["localhost"]


def test_uppercase_in_authority_domain(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<Example.Com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["Example.Com"]


def test_authority_domain_starting_with_hyphen(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<-example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["-example.com"]


def test_authority_domain_ending_with_hyphen(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com-:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com-"]


def test_authority_domain_starting_with_dot(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<.example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [".example.com"]


def test_authority_domain_ending_with_dot(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com.:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com."]


def test_single_char_authority_domain(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<x:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["x"]


def test_authority_domain_starting_with_dot_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:.example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == [".example.com"]


def test_authority_domain_ending_with_dot_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:example.com.:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com."]


def test_authority_domain_starting_with_hyphen_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:-example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["-example.com"]


def test_authority_domain_ending_with_hyphen_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:example.com-:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com-"]


def test_single_char_authority_domain_in_full_fqun(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<mymv:a:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["a"]


def test_non_ascii_in_authority_domain(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<ex\u00e4mple.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["ex\u00e4mple.com"]
