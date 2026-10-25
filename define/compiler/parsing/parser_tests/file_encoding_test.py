# pyright: reportUnusedCallResult=false
"""File encoding parser tests.

Follow parser test authoring rules in parser_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler import ast
from define.compiler.errors import diagnostics, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.parsing.parser_tests.conftest import (
        Parse,
        ParseWithDiagnostics,
    )


def test_bom_at_start(parse: Parse):
    with pytest.raises(parser_exceptions.ByteOrderMarkError) as exc_info:
        parse("\ufeffdefine the potential position<standard:/path>.\n")
    assert exc_info.value.char == "\ufeff"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 1


def test_crlf_line_endings(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("define the potential position<standard:/path>.\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_crlf_line_endings_in_comments(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("# a comment\r\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 12
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 12


def test_carriage_return_in_comment(parse: Parse):
    with pytest.raises(parser_exceptions.CarriageReturnError) as exc_info:
        parse("# comment with\rcarriage return\n")
    assert exc_info.value.char == "\r"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 15


def test_surrogate_character(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\udcff\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_surrogate_range_start_boundary(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\ud800\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_surrogate_range_end_boundary(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/path>.\n\udfff\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_del_character(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\n\x7f\n")
    assert exc_info.value.char == "\x7f"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_non_ascii_character_at_top_level(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential position<standard:/path>.\n☃\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_control_character_after_syntax_error(parse: Parse):
    with pytest.raises(parser_exceptions.ExpectedGlobalDefinition) as exc_info:
        parse("define the potential position<standard:/path>.\nx\x01\n")
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 2


def test_first_non_ascii_byte(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\n\x80\n")
    assert exc_info.value.char == "\x80"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 1


def test_comment_with_zero_width_joiner_in_grapheme_cluster(parse: Parse):
    program = parse(
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
    parse: Parse,
):
    program = parse(
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


def test_variation_selector_after_space_in_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# \ufe0f\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=3, end_line=1, end_column=3),
            character="\ufe0f",
        ),
    ]


def test_invalid_utf8_in_comment(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("# a\udcffb\n" + "define the potential position<standard:/path>.\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 4
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 4


def test_invalid_utf8_in_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvalidEncodingError) as exc_info:
        parse("define the potential position<standard:/a\udcffb>.\n")
    assert exc_info.value.char == "\\xed"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_zero_width_space_in_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<standard:/a\u200bb>.\n")
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_zero_width_space_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<standard:/path>.\u200b\n")
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_zero_width_joiner_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<standard:/path>.\u200d\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_variation_selector_after_terminator(parse: Parse):
    with pytest.raises(parser_exceptions.MissingNewlineAfterTerminator) as exc_info:
        parse("define the potential position<standard:/path>.\ufe0f\n")
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 47
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 47


def test_zero_width_joiner_at_end_of_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<standard:/a\u200d>.\n")
    assert exc_info.value.char == "\u200d"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 42
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 42


def test_variation_selector_at_start_of_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<\ufe0fstandard:/a>.\n")
    assert exc_info.value.char == "\ufe0f"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 31
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 31


def test_comment_with_bidi_isolates_gets_a_diagnostic_for_each(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# isolate-wrapped rtl text: \u2067\u05e9\u05dc\u05d5\u05dd\u2069\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=29, end_line=1, end_column=29),
            character="\u2067",
        ),
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=34, end_line=1, end_column=34),
            character="\u2069",
        ),
    ]


def test_zero_width_space_in_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# a\u200bb\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=4, end_line=1, end_column=4),
            character="\u200b",
        ),
    ]


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


def test_byte_order_mark_inside_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# a\ufeffb\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.ByteOrderMarkInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=4, end_line=1, end_column=4)
        ),
    ]


def test_c1_control_character_in_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# a\u0085b\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.ControlCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=4, end_line=1, end_column=4),
            character="\u0085",
        ),
    ]


def test_zero_width_joiner_before_space_in_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# a\u200d b\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=4, end_line=1, end_column=4),
            character="\u200d",
        ),
    ]


def test_tag_character_after_letter_in_comment_gets_a_diagnostic(
    parse_with_diagnostics: ParseWithDiagnostics,
):
    result = parse_with_diagnostics(
        "# a\U000e0041\n"
        + "define the potential position<mv:define-lang.org:parser:/path>.\n"
    )
    assert result.exception is None
    assert result.program is not None
    assert result.diagnostics == [
        diagnostics.InvisibleCharacterInCommentDiagnostic(
            location=ast.SourceLocation(line=1, column=4, end_line=1, end_column=4),
            character="\U000e0041",
        ),
    ]


def test_comment_with_emoji_zwj_sequence(parse: Parse):
    program = parse(
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


def test_comment_with_direction_marks(parse: Parse):
    program = parse(
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


def test_direction_mark_in_global_name_is_rejected(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("define the potential position<mv:define-lang.org:parser:/a\u061cb>.\n")
    assert exc_info.value.char == "\u061c"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 59
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 59


def test_direction_mark_before_comment_is_rejected(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse("\u200f# comment\n")
    assert exc_info.value.char == "\u200f"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 1
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 1


def test_control_character_where_open_angle_bracket_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position\x01<standard:/path>.\n")
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 30
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 30


def test_control_character_where_terminator_or_brace_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path>\x01\n")
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 46
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 46


def test_control_character_after_block_open(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse("define the potential position<standard:/path> {\x01\n" + "}\n")
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 1
    assert exc_info.value.location.column == 48
    assert exc_info.value.location.end_line == 1
    assert exc_info.value.location.end_column == 48


def test_control_character_in_potential_position_definition_block_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may\x01\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 11
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 11


def test_control_character_where_quality_assignment_block_open_belongs(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where\x01\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 40
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 40


def test_control_character_in_quality_assignment_block_statement(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has\x01\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 15
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 15


def test_control_character_where_quality_assignment_name_type_belongs(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the \x01position</child>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 20
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 20


def test_control_character_where_terminator_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>\x01\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 3
    assert exc_info.value.location.column == 36
    assert exc_info.value.location.end_line == 3
    assert exc_info.value.location.end_column == 36


def test_control_character_after_block_close(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\x01\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 6


def test_control_character_where_block_close_belongs(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential position<standard:/path> {\n"
            + "    it may only contain particles where {\n"
            + "        it has the position</child>.\n"
            + "    }\n"
            + "    \x01\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 5
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 5


def test_control_character_in_trigger_condition(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        this\x01 particle is created.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 13
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 13


def test_control_character_after_position_presence_typed_name(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run>\x01 has a particle.\n"
            + "    } and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 4
    assert exc_info.value.location.column == 26
    assert exc_info.value.location.end_line == 4
    assert exc_info.value.location.end_column == 26


def test_control_character_after_trigger_close_brace(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    }\x01 and it does {\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 5
    assert exc_info.value.location.column == 6
    assert exc_info.value.location.end_line == 5
    assert exc_info.value.location.end_column == 6


def test_control_character_after_move_source(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        move the particle in position<run>\x01 to position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 43
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 43


def test_control_character_in_action_statement(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a\x01 particle in position<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 17
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 17


def test_control_character_in_action_definition_block(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    it\x01 happens when {\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 2
    assert exc_info.value.location.column == 7
    assert exc_info.value.location.end_line == 2
    assert exc_info.value.location.end_column == 7


def test_invisible_character_in_local_name_reference(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in position<r\u200bun>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 40
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 40


def test_control_character_in_reference_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in posi\x01tion<run>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 34
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 34


def test_invisible_character_in_invalid_reference_name(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in position<a\u200b:b>.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\u200b"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 40
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 40


def test_control_character_after_create_particle_reference(parse: Parse):
    with pytest.raises(parser_exceptions.ControlCharacterError) as exc_info:
        parse(
            "define the potential action<mv:define-lang.org:parser:/act> {\n"
            + "    define the position<run>.\n"
            + "    it happens when {\n"
            + "        the position<run> has a particle.\n"
            + "    } and it does {\n"
            + "        create a particle in position<run>\x01.\n"
            + "    }\n"
            + "}\n"
        )
    assert exc_info.value.char == "\x01"
    assert exc_info.value.location.line == 6
    assert exc_info.value.location.column == 43
    assert exc_info.value.location.end_line == 6
    assert exc_info.value.location.end_column == 43


def test_invisible_character_in_encoding_quality_assignment_name_type(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has the encod\u200bing</decimal>.\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 2
    assert error.value.location.column == 21
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 21


def test_invisible_character_in_it_has_the(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        _ = parse(
            "define the potential literal<mv:define-lang.org:parser:/decimal> {\n"
            + "    it has\u200b the encoding</decimal>.\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 2
    assert error.value.location.column == 11
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 11


def test_invisible_character_after_escape_in_literal(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + '        set the value of position<dest> to literal</text>"a\\"\u202e".\n'
            + "    }\n}\n"
        )
    assert error.value.char == "\u202e"
    assert error.value.location.line == 5
    assert error.value.location.column == 62
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 62


def test_invisible_character_escaped_in_literal(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + '        set the value of position<dest> to literal</text>"a\\\u202e".\n'
            + "    }\n}\n"
        )
    assert error.value.char == "\u202e"
    assert error.value.location.line == 5
    assert error.value.location.column == 61
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 61


def test_invisible_character_before_literal_content(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + '        set the value of position<dest> to literal</text>\u202e"a".\n'
            + "    }\n}\n"
        )
    assert error.value.char == "\u202e"
    assert error.value.location.line == 5
    assert error.value.location.column == 58
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 58


def test_invisible_character_in_value_source_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the potential action<mv:define-lang.org:parser:/set_value> {\n"
            + "    it happens when {\n"
            + "        this particle is created.\n"
            + "    } and it does {\n"
            + "        set the value of position<dest> to posi\u200btion<x>.\n"
            + "    }\n}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 5
    assert error.value.location.column == 48
    assert error.value.location.end_line == 5
    assert error.value.location.end_column == 48


def test_invisible_character_in_view_direction_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is\u200b read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 3
    assert error.value.location.column == 14
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 14


def test_invisible_character_in_view_quality_assignment_block(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the view<left> {\n"
            + "        it is read.\n"
            + "        it may\u200b only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 4
    assert error.value.location.column == 15
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 15


def test_invisible_character_in_view_definition(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    define the vi\u200bew<left> {\n"
            + "        it is read.\n"
            + "        it may only contain particles where {\n"
            + "            it has the value</number>.\n"
            + "        }\n"
            + "    }\n"
            + "    it does {\n"
            + "        execute the encoding operation.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 2
    assert error.value.location.column == 18
    assert error.value.location.end_line == 2
    assert error.value.location.end_column == 18


def test_invisible_character_in_operation_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute\u200b the operation</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 3
    assert error.value.location.column == 16
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 16


def test_invisible_character_in_operation_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the opera\u200btion</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 3
    assert error.value.location.column == 26
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 26


def test_invisible_character_in_encoding_operation_name_type(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the encoding_operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the encoding_opera\u200btion</other>.\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 3
    assert error.value.location.column == 35
    assert error.value.location.end_line == 3
    assert error.value.location.end_column == 35


def test_invisible_character_in_operation_argument_view_name_type(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            with vi\u200bew<a> looking at view<left>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 4
    assert error.value.location.column == 20
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 20


def test_invisible_character_in_operation_argument_source_name_type(
    parse: Parse,
):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            with view<a> looking at posi\u200btion<p>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 4
    assert error.value.location.column == 41
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 41


def test_invisible_character_in_operation_argument_statement(parse: Parse):
    with pytest.raises(parser_exceptions.InvisibleCharacterError) as error:
        parse(
            "define the operation<mv:define-lang.org:parser:/add> {\n"
            + "    it does {\n"
            + "        execute the operation</other> {\n"
            + "            wi\u200bth view<a> looking at view<left>.\n"
            + "        }\n"
            + "    }\n"
            + "}\n"
        )
    assert error.value.char == "\u200b"
    assert error.value.location.line == 4
    assert error.value.location.column == 15
    assert error.value.location.end_line == 4
    assert error.value.location.end_column == 15
