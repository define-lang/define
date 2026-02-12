# pyright: reportUnusedCallResult=false
"""Global name structure parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions
from define.compiler.parser_tests.test_helpers import get_tokens_by_type


def test_full_fqun(p: parser.Parser) -> None:
    tree = p.parse(
        "define the potential position<my_mv:example.com:my_lib:/some/path>.\n"
    )
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == ["my_mv"]
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]


def test_authority_universe_no_multiverse(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com:my_lib:/some/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == []
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]


def test_standard_form(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<standard:/some/path>.\n")
    assert get_tokens_by_type(tree, "MULTIVERSE_NAME") == []
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == []
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["standard"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["some", "path"]


def test_authority_with_path(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<example.com/org/repo:my_lib:/foo>.\n")
    assert get_tokens_by_type(tree, "AUTHORITY_DOMAIN") == ["example.com"]
    assert get_tokens_by_type(tree, "AUTHORITY_PATH_SEGMENT") == ["org", "repo"]
    assert get_tokens_by_type(tree, "UNIVERSE_NAME") == ["my_lib"]
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["foo"]


def test_multi_segment_global_path(p: parser.Parser) -> None:
    tree = p.parse("define the potential position<standard:/a/b/c/d>.\n")
    assert get_tokens_by_type(tree, "PATH_SEGMENT") == ["a", "b", "c", "d"]


def test_missing_close_angle(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
        p.parse("define the potential position<standard:/path.\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.column == 46


def test_missing_close_angle_in_three_part_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
        p.parse("define the potential position<example.com:my_lib:/path.\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.column == 56


def test_missing_close_angle_in_full_fqun(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingCloseAngleBracketError) as exc_info:
        p.parse("define the potential position<mymv:example.com:my_lib:/path.\n")
    assert str(exc_info.value.token) == "\n"
    assert exc_info.value.column == 61


def test_missing_open_angle(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.MissingOpenAngleBracketError) as exc_info:
        p.parse("define the potential positionstandard:/path>.\n")
    assert str(exc_info.value.token) == "standard"
    assert exc_info.value.column == 30


def test_empty_name_content(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.EmptyNameError) as exc_info:
        p.parse("define the potential position<>.\n")
    assert str(exc_info.value.token) == ">"
    assert exc_info.value.column == 31


def test_path_not_starting_with_slash(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:path>.\n")
    assert str(exc_info.value.token) == "standard"
    assert exc_info.value.column == 31


def test_empty_path_segment(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<standard:/a//b>.\n")
    assert str(exc_info.value.token) == "/b"
    assert exc_info.value.column == 43


def test_local_name_not_valid_in_definitions(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidGlobalNamePathError) as exc_info:
        p.parse("define the potential position<my_name>.\n")
    assert str(exc_info.value.token) == "my_name"
    assert exc_info.value.column == 31
