from __future__ import annotations

import pytest

from define.compiler.parsing import invisible_characters


@pytest.mark.parametrize(
    "text",
    [
        "define the potential value<mv:define-lang.org:x:/v>.",
        "# \u05e9\u05dc\u05d5\u05dd",
        "\U0001f468\u200d\U0001f469\u200d\U0001f467",
        "\u2764\ufe0f\u200d\U0001f525",
        "1\ufe0f\u20e3",
        "\U0001f44d\U0001f3fd",
        "\u0645\u06cc\u200c\u062e",
        "\u200e\u200f\u061c",
    ],
    ids=[
        "ascii",
        "hebrew",
        "emoji_zwj_sequence",
        "zwj_after_variation_selector",
        "keycap",
        "skin_tone",
        "persian_zwnj",
        "direction_marks",
    ],
)
def test_allowed_text_has_no_forbidden_character(text: str):
    assert invisible_characters.first_forbidden_index(text) is None


@pytest.mark.parametrize(
    ("text", "index"),
    [
        ("a\u200bb", 1),
        ("a\u2067b\u2069", 1),
        ("\u202e", 0),
        ("a\u00a0b", 1),
        ("\u3164", 0),
        ("\ufeff", 0),
        ("a\u0085", 1),
        ("a\U000e0041", 1),
        ("a\ufe00", 1),
        ("a\U000e0100", 1),
        ("\U000f0000", 0),
        ("\U0001fffe", 0),
        ("\U0001f600\u200b", 1),
    ],
    ids=[
        "zero_width_space",
        "bidi_isolate",
        "bidi_override",
        "no_break_space",
        "hangul_filler",
        "byte_order_mark",
        "c1_control",
        "tag_character",
        "variation_selector_1",
        "supplementary_variation_selector",
        "astral_private_use",
        "astral_noncharacter",
        "invisible_after_emoji",
    ],
)
def test_invisible_character_is_forbidden(text: str, index: int):
    assert invisible_characters.first_forbidden_index(text) == index


@pytest.mark.parametrize(
    ("text", "index"),
    [
        ("\u200da", 0),
        ("a\u200d", 1),
        ("a\u200d b", 1),
        ("\ufe0f", 0),
        (" \ufe0f", 1),
        ("a\u200c\u200cb", 1),
    ],
    ids=[
        "joiner_at_start",
        "joiner_at_end",
        "joiner_before_space",
        "variation_selector_at_start",
        "variation_selector_after_space",
        "joiner_after_joiner",
    ],
)
def test_joiner_or_variation_selector_out_of_context_is_forbidden(
    text: str, index: int
):
    assert invisible_characters.first_forbidden_index(text) == index
