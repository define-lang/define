# pyright: reportUnusedCallResult=false
"""Path segment format parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_underscores_in_segments(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<my_mv:ex.com:my_lib:/a_b/c_d>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["a_b", "c_d"]


def test_digits_in_path_segments(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<standard:/item2>.\n")
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["item2"]


def test_path_segment_starting_with_digit(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:/2bad>.\n")
    assert str(exc_info.value.token) == "2bad"
    assert exc_info.value.column == 41


def test_invalid_chars_in_path_uppercase(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
        p.parse("define the potential position<standard:/BadName>.\n")
    assert exc_info.value.char == "B"
    assert exc_info.value.column == 41


def test_invalid_chars_in_path_hyphen(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:/bad-name>.\n")
    assert str(exc_info.value.token) == "-name"
    assert exc_info.value.column == 44


def test_invalid_chars_in_path_dot(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:/bad.name>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 44


def test_invalid_chars_in_path_tilde(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:/bad~name>.\n")
    assert str(exc_info.value.token) == "~name"
    assert exc_info.value.column == 44


def test_invalid_chars_in_path_special(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        p.parse("define the potential position<standard:/bad!name>.\n")
    assert exc_info.value.char == "!"
    assert exc_info.value.column == 44


def test_invalid_chars_in_path_hyphen_in_three_part_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<example.com:my_lib:/bad-name>.\n")
    assert str(exc_info.value.token) == "-name"
    assert exc_info.value.column == 54


def test_invalid_chars_in_path_hyphen_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<mymv:example.com:my_lib:/bad-name>.\n")
    assert str(exc_info.value.token) == "-name"
    assert exc_info.value.column == 59


def test_invalid_chars_in_path_special_in_three_part_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        p.parse("define the potential position<example.com:my_lib:/bad!name>.\n")
    assert exc_info.value.char == "!"
    assert exc_info.value.column == 54


def test_invalid_chars_in_path_special_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidCharacterError) as exc_info:
        p.parse("define the potential position<mymv:example.com:my_lib:/bad!name>.\n")
    assert exc_info.value.char == "!"
    assert exc_info.value.column == 59
