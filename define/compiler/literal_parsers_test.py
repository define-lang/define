from __future__ import annotations

import pytest

from define.compiler import constants, literal_parsers

_PARSE_BINARY_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.BINARY_ASCII_ENCODING, constants.BINARY_ASCII_ENCODING)
]
_PARSE_BINARY_ASCII_AS_DECIMAL_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.BINARY_ASCII_ENCODING, constants.DECIMAL_ASCII_ENCODING)
]
_PARSE_BINARY_ASCII_AS_INTEGER_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.BINARY_ASCII_ENCODING, constants.INTEGER_ASCII_ENCODING)
]
_PARSE_BINARY_ASCII_AS_NATURAL_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.BINARY_ASCII_ENCODING, constants.NATURAL_ASCII_ENCODING)
]
_PARSE_BOOLEAN_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.BOOLEAN_ASCII_ENCODING, constants.BOOLEAN_ASCII_ENCODING)
]
_PARSE_CODE_POINT_ASCII_AS_SCALAR_UTF8 = literal_parsers.LITERAL_PARSERS[
    (constants.CODE_POINT_ASCII_ENCODING, constants.SCALAR_UTF8_ENCODING)
]
_PARSE_DECIMAL_ASCII_AS_BINARY_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.DECIMAL_ASCII_ENCODING, constants.BINARY_ASCII_ENCODING)
]
_PARSE_DECIMAL_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.DECIMAL_ASCII_ENCODING, constants.DECIMAL_ASCII_ENCODING)
]
_PARSE_DECIMAL_ASCII_AS_INTEGER_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.DECIMAL_ASCII_ENCODING, constants.INTEGER_ASCII_ENCODING)
]
_PARSE_DECIMAL_ASCII_AS_NATURAL_ASCII = literal_parsers.LITERAL_PARSERS[
    (constants.DECIMAL_ASCII_ENCODING, constants.NATURAL_ASCII_ENCODING)
]
_PARSE_UTF8_AS_SCALAR_UTF8 = literal_parsers.LITERAL_PARSERS[
    (constants.UTF8_ENCODING, constants.SCALAR_UTF8_ENCODING)
]


@pytest.mark.parametrize("content", ["0", "1", "1001"])
def test_binary_ascii_accepts(content: str):
    assert _PARSE_BINARY_ASCII(content) == content


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("", "there must be at least one bit", 0),
        ("102", "only the bits 0 and 1 are allowed", 2),
        ("0b1", "only the bits 0 and 1 are allowed", 1),
        ("1 0", "only the bits 0 and 1 are allowed", 1),
        ("00", "binary values are written without leading zeros", 0),
        ("0101", "binary values are written without leading zeros", 0),
    ],
)
def test_binary_ascii_rejects(content: str, reason: str, content_index: int):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_BINARY_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize(
    ("content", "decimal"),
    [("0", "0"), ("1", "1"), ("1011", "11"), ("100000000", "256")],
)
def test_binary_ascii_as_decimal_ascii_accepts(content: str, decimal: str):
    assert _PARSE_BINARY_ASCII_AS_DECIMAL_ASCII(content) == decimal


def test_binary_ascii_as_decimal_ascii_rejects():
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_BINARY_ASCII_AS_DECIMAL_ASCII("0101")
    assert error.value.reason == "binary values are written without leading zeros"
    assert error.value.content_index == 0


@pytest.mark.parametrize(
    ("content", "integer"),
    [("0", "0"), ("1011", "11"), ("-1", "-1"), ("-1011", "-11")],
)
def test_binary_ascii_as_integer_ascii_accepts(content: str, integer: str):
    assert _PARSE_BINARY_ASCII_AS_INTEGER_ASCII(content) == integer


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("-", "there must be at least one bit", 1),
        ("--1", "only the bits 0 and 1 are allowed", 1),
        ("-102", "only the bits 0 and 1 are allowed", 3),
        ("1-1", "only the bits 0 and 1 are allowed", 1),
        ("-01", "binary values are written without leading zeros", 1),
        ("-0", "zero is written without a minus sign", 0),
    ],
)
def test_binary_ascii_as_integer_ascii_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_BINARY_ASCII_AS_INTEGER_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize(("content", "natural"), [("0", "0"), ("1011", "11")])
def test_binary_ascii_as_natural_ascii_accepts(content: str, natural: str):
    assert _PARSE_BINARY_ASCII_AS_NATURAL_ASCII(content) == natural


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("-1", "negative numbers are not allowed", 0),
        ("0101", "binary values are written without leading zeros", 0),
    ],
)
def test_binary_ascii_as_natural_ascii_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_BINARY_ASCII_AS_NATURAL_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize("content", ["true", "false"])
def test_boolean_ascii_accepts(content: str):
    assert _PARSE_BOOLEAN_ASCII(content) == content


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("", "a boolean is either true or false", 0),
        ("True", "booleans are written in lowercase", 0),
        ("fALSE", "booleans are written in lowercase", 1),
        ("yes", "a boolean is either true or false", 0),
        ("1", "a boolean is either true or false", 0),
        ("true ", "a boolean is either true or false", 0),
    ],
)
def test_boolean_ascii_rejects(content: str, reason: str, content_index: int):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_BOOLEAN_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize(
    "content", ["5", "-5", "0", "5.25", "-0.5", "0.05", "10", "100.001", "123456789012"]
)
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
        ("05", "numbers are written without leading zeros", 0),
        ("00", "numbers are written without leading zeros", 0),
        ("-05.5", "numbers are written without leading zeros", 1),
        ("5.0", "whole numbers are written without a decimal point", 1),
        ("-10.00", "whole numbers are written without a decimal point", 3),
        (
            "5.50",
            "numbers are written without trailing zeros after the decimal point",
            3,
        ),
        ("-0", "zero is written without a minus sign", 0),
        ("\u0663", "only the digits 0 through 9 are allowed", 0),
        ("1\uff15", "only the digits 0 through 9 are allowed", 1),
    ],
)
def test_decimal_ascii_rejects(content: str, reason: str, content_index: int):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_DECIMAL_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize(
    ("content", "binary"),
    [("0", "0"), ("1", "1"), ("11", "1011"), ("256", "100000000")],
)
def test_decimal_ascii_as_binary_ascii_accepts(content: str, binary: str):
    assert _PARSE_DECIMAL_ASCII_AS_BINARY_ASCII(content) == binary


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("-3", "negative numbers are not allowed", 0),
        ("2.5", "only whole numbers are allowed", 1),
        ("-2.5", "negative numbers are not allowed", 0),
        ("03", "numbers are written without leading zeros", 0),
    ],
)
def test_decimal_ascii_as_binary_ascii_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_DECIMAL_ASCII_AS_BINARY_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize("content", ["0", "5", "-5", "123456789012"])
def test_decimal_ascii_as_integer_ascii_accepts(content: str):
    assert _PARSE_DECIMAL_ASCII_AS_INTEGER_ASCII(content) == content


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("2.5", "only whole numbers are allowed", 1),
        ("-2.5", "only whole numbers are allowed", 2),
        ("03", "numbers are written without leading zeros", 0),
    ],
)
def test_decimal_ascii_as_integer_ascii_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_DECIMAL_ASCII_AS_INTEGER_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize("content", ["0", "5", "123456789012"])
def test_decimal_ascii_as_natural_ascii_accepts(content: str):
    assert _PARSE_DECIMAL_ASCII_AS_NATURAL_ASCII(content) == content


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("-3", "negative numbers are not allowed", 0),
        ("2.5", "only whole numbers are allowed", 1),
        ("-2.5", "negative numbers are not allowed", 0),
        ("03", "numbers are written without leading zeros", 0),
    ],
)
def test_decimal_ascii_as_natural_ascii_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_DECIMAL_ASCII_AS_NATURAL_ASCII(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index


@pytest.mark.parametrize("content", ["q", " ", '"', "\n", "\u00e9", "\U0001f600"])
def test_utf8_as_scalar_utf8_accepts(content: str):
    assert _PARSE_UTF8_AS_SCALAR_UTF8(content) == content


@pytest.mark.parametrize(
    ("content", "content_index"),
    [
        ("", 0),
        ("qq", 1),
        ("e\u0301", 1),
        ("\U0001f468\u200d\U0001f467", 1),
    ],
)
def test_utf8_as_scalar_utf8_rejects(content: str, content_index: int):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_UTF8_AS_SCALAR_UTF8(content)
    assert error.value.reason == "there must be exactly one scalar"
    assert error.value.content_index == content_index


@pytest.mark.parametrize(
    ("content", "scalar"),
    [
        ("0", "\x00"),
        ("9", "\t"),
        ("71", "q"),
        ("E9", "\u00e9"),
        ("301", "\u0301"),
        ("D7FF", "\ud7ff"),
        ("E000", "\ue000"),
        ("1F600", "\U0001f600"),
        ("10FFFF", "\U0010ffff"),
    ],
)
def test_code_point_ascii_as_scalar_utf8_accepts(content: str, scalar: str):
    assert _PARSE_CODE_POINT_ASCII_AS_SCALAR_UTF8(content) == scalar


@pytest.mark.parametrize(
    ("content", "reason", "content_index"),
    [
        ("", "there must be at least one hex digit", 0),
        ("e9", "hex digits are written in uppercase", 0),
        ("1f600", "hex digits are written in uppercase", 1),
        ("U+0301", "'U' is not allowed in a code point", 0),
        ("E9G", "'G' is not allowed in a code point", 2),
        ("0301", "code points are written without leading zeros", 0),
        ("00", "code points are written without leading zeros", 0),
        ("D800", "surrogates are not scalars", 0),
        ("DFFF", "surrogates are not scalars", 0),
        ("110000", "code points end at 10FFFF", 0),
        ("FFFFFFFFFFFFFFFFFFFF", "code points end at 10FFFF", 0),
    ],
)
def test_code_point_ascii_as_scalar_utf8_rejects(
    content: str, reason: str, content_index: int
):
    with pytest.raises(literal_parsers.LiteralParseError) as error:
        _ = _PARSE_CODE_POINT_ASCII_AS_SCALAR_UTF8(content)
    assert error.value.reason == reason
    assert error.value.content_index == content_index
