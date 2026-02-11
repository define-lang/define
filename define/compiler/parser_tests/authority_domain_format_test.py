# pyright: reportUnusedCallResult=false
"""Authority domain format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_authority_domain_with_dots_and_hyphens(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<my-host.example.com:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["my-host.example.com"]


def test_authority_domain_without_dot(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<localhost:my_lib:/path>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["localhost"]


def test_uppercase_in_authority_domain(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
        p.parse("define the potential position<Example.Com:my_lib:/path>.\n")
    assert exc_info.value.char == "E"
    assert exc_info.value.column == 31


def test_authority_domain_starting_with_hyphen(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<-example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "-example.com"
    assert exc_info.value.column == 31


def test_authority_domain_ending_with_hyphen(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<example.com-:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "-"
    assert exc_info.value.column == 42


def test_authority_domain_starting_with_dot(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<.example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 31


def test_authority_domain_ending_with_dot(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<example.com.:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 42


def test_single_char_authority_domain(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<x:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "x"
    assert exc_info.value.column == 31


def test_authority_domain_starting_with_dot_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<mymv:.example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 36


def test_authority_domain_ending_with_dot_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<mymv:example.com.:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 47


def test_authority_domain_starting_with_hyphen_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<mymv:-example.com:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "-example.com"
    assert exc_info.value.column == 36


def test_authority_domain_ending_with_hyphen_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<mymv:example.com-:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "-"
    assert exc_info.value.column == 47


def test_single_char_authority_domain_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityDomainError) as exc_info:
        p.parse("define the potential position<mymv:a:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "a"
    assert exc_info.value.column == 36


def test_non_ascii_in_authority_domain(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        p.parse("define the potential position<ex\u00e4mple.com:my_lib:/path>.\n")
    assert exc_info.value.char == "\u00e4"
    assert exc_info.value.column == 33
