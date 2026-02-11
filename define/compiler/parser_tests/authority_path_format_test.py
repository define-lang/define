# pyright: reportUnusedCallResult=false
"""Authority path parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

import pytest

from define.compiler import parser, parser_exceptions


def test_invalid_chars_in_authority_path_uppercase(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.UppercaseNotAllowedError) as exc_info:
        p.parse("define the potential position<example.com/Bad:my_lib:/path>.\n")
    assert exc_info.value.char == "B"
    assert exc_info.value.column == 43


def test_invalid_chars_in_authority_path_angle(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
        p.parse("define the potential position<example.com/ba<d:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "<"
    assert exc_info.value.column == 45


def test_authority_path_segment_starting_with_dot(p: parser.Parser) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
        p.parse("define the potential position<example.com/.hidden:my_lib:/path>.\n")
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 43


def test_authority_path_segment_starting_with_dot_in_full_fqun(
    p: parser.Parser,
) -> None:
    with pytest.raises(parser_exceptions.InvalidAuthorityPathError) as exc_info:
        p.parse(
            "define the potential position<mymv:example.com/.hidden:my_lib:/path>.\n"
        )
    assert str(exc_info.value.token) == "."
    assert exc_info.value.column == 48
