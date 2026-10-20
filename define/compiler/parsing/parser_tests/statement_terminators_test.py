# pyright: reportUnusedCallResult=false
"""Statement terminator parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.errors import parser_exceptions
from define.compiler.parsing.parser_tests.test_helpers import get_tokens_by_type

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_valid_terminator(parse: Parse):
    tree = parse("define the potential position<mv:define-lang.org:parser:/path>.\n")
    assert get_tokens_by_type(tree, "GLOBAL_NAME_CONTENT") == [
        "mv:define-lang.org:parser:/path"
    ]


def test_missing_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingTerminatorOrBrace) as exc_info:
        native_parse("define the potential position<standard:/path>\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_column == 46


def test_missing_newline_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        native_parse("define the potential position<standard:/path>.")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_column == 47


def test_missing_newline_after_last_definition(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAtEof) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/first>.\n"
            + "define the potential position<mv:define-lang.org:parser:/second>."
        )
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 66
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 66


def test_missing_newline_between_global_definitions(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse(
            "define the potential position<mv:define-lang.org:parser:/path>.define the potential action<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_column == 91


def test_double_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>..\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_column == 65


def test_comment_directly_after_terminator(native_parse_lark_wrong: NativeParse):
    with pytest.raises(parser_exceptions.MissingSpaceBeforeComment) as exc_info:
        native_parse_lark_wrong(
            "define the potential position<mv:define-lang.org:parser:/path>.# comment\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 65


def test_letter_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>.x\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 65


def test_non_ascii_character_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/path>.é\n"
        )
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 64
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 65


def test_space_before_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingCloseAngleBracket) as exc_info:
        parse("define the potential position<mv:my.domain.com:my_lib:/some_name .\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 67
    assert exc_info.value.location.end_column == 67
    assert exc_info.value.name == "mv:my.domain.com:my_lib:/some_name ."


def test_trailing_space_before_newline(parse: Parse):
    with pytest.raises(parser_exceptions.TrailingWhitespaceError) as exc_info:
        parse("define the potential position<standard:/path>. \n")
    assert exc_info.value.char == " "
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_column == 48


def test_missing_terminator_after_typed_reference_in_position_constraint(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.MissingTerminator) as exc_info:
        parse(
            "define the potential position<my_lib:/hello/hello>.\n"
            + "define the potential position<my_lib:/sub/sub> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the action<std:/path/sub>\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 41
    assert exc_info.value.location.end_column == 41
