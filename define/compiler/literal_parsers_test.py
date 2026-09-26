from __future__ import annotations

import pytest

from define.compiler import constants, literal_parsers

_PARSE_DECIMAL_ASCII = literal_parsers.LITERAL_PARSERS[
    constants.DECIMAL_ASCII_ENCODING, constants.DECIMAL_ASCII_ENCODING
]


@pytest.mark.parametrize("content", ["5", "-5", "0", "5.25", "-0.5", "123456789012"])
def test_decimal_ascii_accepts(content: str):
    assert _PARSE_DECIMAL_ASCII(content) == content


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("", "there must be at least one digit", 0),
        ("+5", "positive numbers are written without a +", 0),
        ("5+3", "'+' is not allowed in a number", 1),
        ("-", "there must be a digit after the minus sign", 0),
        ("--5", "a minus sign may only appear at the start", 1),
        ("5-3", "a minus sign may only appear at the start", 1),
        (".5", "there must be a digit before the decimal point", 0),
        ("-.5", "there must be a digit before the decimal point", 1),
        ("5.", "there must be a digit after the decimal point", 1),
        ("1.2.3", "a number may have only one decimal point", 3),
        ("1e5", "'e' is not allowed in a number", 1),
        ("1,000", "',' is not allowed in a number", 1),
        ("5 ", "' ' is not allowed in a number", 1),
        (" 5", "' ' is not allowed in a number", 0),
        ("5\n", "'\n' is not allowed in a number", 1),
        ("\u0663", "only the digits 0 through 9 are allowed", 0),
        ("1\uff15", "only the digits 0 through 9 are allowed", 1),
    ],
)
def test_decimal_ascii_rejects(content: str, reason: str, content_index: int):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_DECIMAL_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index
