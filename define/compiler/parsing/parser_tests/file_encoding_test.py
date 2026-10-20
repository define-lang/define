# pyright: reportUnusedCallResult=false
"""File encoding parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import NativeParse, Parse


def test_bom_at_start(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        native_parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert exc_info.value.char == "\ufeff"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 1


def test_crlf_line_endings(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        native_parse("define the potential position<standard:/path>.\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_crlf_line_endings_in_comments(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        native_parse("# a comment\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 12
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 12


def test_carriage_return_in_comment(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        native_parse("# comment with\rcarriage return\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 15


def test_surrogate_character(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        native_parse("define the potential position<standard:/path>.\n\udcff\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_surrogate_range_start_boundary(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        native_parse("define the potential position<standard:/path>.\n\ud800\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_surrogate_range_end_boundary(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        native_parse("define the potential position<standard:/path>.\n\udfff\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_del_character(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        native_parse("define the potential position<standard:/path>.\n\x7f\n")
    assert exc_info.value.char == "\x7f"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_non_ascii_character_at_top_level(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("define the potential position<standard:/path>.\n☃\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_control_character_after_syntax_error(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        native_parse("define the potential position<standard:/path>.\nx\x01\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 2


def test_first_non_ascii_byte(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        native_parse("define the potential position<standard:/path>.\n\x80\n")
    assert exc_info.value.char == "\x80"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_comment_with_zero_width_joiner_in_grapheme_cluster(native_parse: NativeParse):
    program = native_parse(
        "# devanagari ligature with ZWJ: \u0915\u094d\u200d\u0937\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=63
    )


def test_comment_with_variation_selector_after_visible_character(
    native_parse: NativeParse,
):
    program = native_parse(
        "# heart: \u2764\ufe0f, and joined: \u2764\ufe0f\u200d\U0001f525\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=63
    )


def test_variation_selector_after_space_in_comment_is_rejected(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "# \ufe0f\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\ufe0f"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 3
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 3


def test_invalid_utf8_in_comment(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        native_parse(
            "# a\udcffb\n" + "define the potential position<standard:/path>.\n"
        )
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_invalid_utf8_in_name(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        native_parse("define the potential position<standard:/a\udcffb>.\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_zero_width_space_in_name(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse("define the potential position<standard:/a\u200bb>.\n")
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_zero_width_space_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse("define the potential position<standard:/path>.\u200b\n")
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_zero_width_joiner_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse("define the potential position<standard:/path>.\u200d\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_variation_selector_after_terminator(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        native_parse("define the potential position<standard:/path>.\ufe0f\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_zero_width_joiner_at_end_of_name(native_parse_lark_wrong: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse_lark_wrong("define the potential position<standard:/a\u200d>.\n")
    assert exc_info.value.char == "\u200d"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_variation_selector_at_start_of_name(native_parse_lark_wrong: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse_lark_wrong("define the potential position<\ufe0fstandard:/a>.\n")
    assert exc_info.value.char == "\ufe0f"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_comment_with_bidi_isolates_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "# isolate-wrapped rtl text: \u2067\u05e9\u05dc\u05d5\u05dd\u2069\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\u2067"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 29
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 29


def test_zero_width_space_in_comment_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "# a\u200bb\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_bidi_override_in_literal_content_is_rejected(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<p>.\n"
            + "    it happens when {\n"
            + "        the position<p> has a particle.\n"
            + "    } and it does {\n"
            + '        set the value of position<p> to literal</number>"1\u202e2".\n'
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u202e"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 59
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 59


def test_byte_order_mark_inside_comment_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        native_parse(
            "# a\ufeffb\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\ufeff"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_c1_control_character_in_comment_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        native_parse(
            "# a\u0085b\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\u0085"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_zero_width_joiner_before_space_in_comment_is_rejected(
    native_parse: NativeParse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "# a\u200d b\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\u200d"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_tag_character_after_letter_in_comment_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "# a\U000e0041\n"
            + "define the potential position<mv:define-lang.org:parser:/path>.\n"
        )
    assert exc_info.value.char == "\U000e0041"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_comment_with_emoji_zwj_sequence(native_parse: NativeParse):
    program = native_parse(
        "# family: \U0001f468\u200d\U0001f469\u200d\U0001f467\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=63
    )


def test_comment_with_direction_marks(native_parse: NativeParse):
    program = native_parse(
        "# \u05e9\u05dc\u05d5\u05dd ok\u200f. \u200eabc \u061c\u0645\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    [definition] = program.definitions
    assert (
        definition.typed_name.full_typed_name
        == "position<mv:define-lang.org:parser:/path>"
    )
    assert definition.location == ast.SourceLocation(
        line=2, column=1, end_line=2, end_column=63
    )


def test_direction_mark_in_literal_content_is_rejected(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<p>.\n"
            + "    it happens when {\n"
            + "        the position<p> has a particle.\n"
            + "    } and it does {\n"
            + '        set the value of position<p> to literal</number>"1\u200f2".\n'
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u200f"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 59
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 59


def test_direction_mark_in_local_name_is_rejected(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<a\u200eb>.\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u200e"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 26


def test_direction_mark_in_global_name_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse(
            "define the potential position<mv:define-lang.org:parser:/a\u061cb>.\n"
        )
    assert exc_info.value.char == "\u061c"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 59
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 59


def test_direction_mark_before_comment_is_rejected(native_parse: NativeParse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        native_parse("\u200f# comment\n")
    assert exc_info.value.char == "\u200f"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 1
