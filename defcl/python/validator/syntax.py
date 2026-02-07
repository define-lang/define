"""Syntax validation for Define Configuration Language (DCL) files."""

import os
from functools import cached_property
from pathlib import Path

import lark
from lark import exceptions

_GRAMMAR_PATH = Path(__file__).parent.parent / "grammar.lark"


class DCLSyntaxError(Exception):
    """Base class for DCL syntax errors."""

    label: str = "Syntax Error"
    context: str
    line: int
    column: int

    def __init__(self, context: str, line: int, column: int) -> None:
        """Initialize the syntax error with location and context information."""
        super().__init__(context, line, column)
        self.context = context
        self.line = line
        self.column = column


class DCLTokenError(DCLSyntaxError):
    """Base class for DCL syntax errors caused by unexpected tokens."""

    token: lark.Token

    def __init__(self, context: str, line: int, column: int, token: lark.Token) -> None:
        """Initialize with the unexpected token."""
        super().__init__(context, line, column)
        self.token = token


class DCLCharError(DCLSyntaxError):
    """Base class for DCL syntax errors caused by unexpected characters."""

    char: str

    def __init__(self, context: str, line: int, column: int, char: str) -> None:
        """Initialize with the unexpected character."""
        super().__init__(context, line, column)
        self.char = char


class BooleanNotSupportedError(DCLTokenError):
    """Raised when true/false boolean literals are used."""

    label: str = "Boolean literals not supported - use enums instead"


class InvalidEnumCaseError(DCLTokenError):
    """Raised when enum values are not ALL_CAPS."""

    label: str = "Enum values must be ALL_CAPS"


class InvalidFieldNameTokenError(DCLTokenError):
    """Raised when field names don't follow naming rules (token error)."""

    label: str = "Invalid field name"


class InvalidFieldNameError(DCLCharError):
    """Raised when field names don't follow naming rules (character error)."""

    label: str = "Invalid field name"


class SingleQuotesNotAllowedError(DCLCharError):
    """Raised when single quotes are used instead of double quotes."""

    label: str = "Use double quotes for strings"


class UnterminatedStringError(DCLCharError):
    """Raised when a string contains an unescaped newline."""

    label: str = "Unterminated string - use \\n for newlines"


class InvalidNumberFormatError(DCLTokenError):
    """Raised when numbers use unsupported formats (token error)."""

    label: str = "Invalid number format"


class InvalidNumberFormatCharError(DCLCharError):
    """Raised when numbers use unsupported formats (character error)."""

    label: str = "Invalid number format"


class MissingColonError(DCLTokenError):
    """Raised when colon is missing between field name and value."""

    label: str = "Missing colon after field name"


class InvalidSeparatorError(DCLTokenError):
    """Raised when invalid separators like comma are used (token error)."""

    label: str = "Invalid separator"


class InvalidSeparatorCharError(DCLCharError):
    """Raised when invalid separators like semicolon are used (character error)."""

    label: str = "Invalid separator"


class TabNotAllowedError(DCLCharError):
    """Raised when tab characters are used."""

    label: str = "Tabs not allowed - use spaces"


class CarriageReturnNotAllowedError(DCLCharError):
    """Raised when carriage return characters are used."""

    label: str = "Carriage returns not allowed - use LF only"


class AngleBracketsNotAllowedError(DCLCharError):
    """Raised when angle brackets are used instead of curly braces."""

    label: str = "Use curly braces {} for messages"


class ScalarAtToplevelError(DCLTokenError):
    """Raised when a scalar value appears at the top level."""

    label: str = "Top-level values must be messages"


class ByteOrderMarkError(DCLCharError):
    """Raised when a byte order mark is present."""

    label: str = "Byte order mark not allowed"


_TOKEN_ERROR_EXAMPLES: dict[type[DCLTokenError], list[str]] = {
    MissingColonError: [
        'a: {\n    b "x"\n}',
        "a {\n    b: 1\n}",
    ],
    BooleanNotSupportedError: [
        "a: {\n    b: true\n}",
        "a: {\n    b: false\n}",
    ],
    InvalidEnumCaseError: [
        "a: {\n    b: active\n}",
        "a: {\n    b: Active\n}",
    ],
    InvalidFieldNameTokenError: [
        "a: {\n    Foo: 1\n}",
        "a: {\n    1a: 1\n}",
    ],
    InvalidNumberFormatError: [
        "a: {\n    b: 0x1A\n}",
        "a: {\n    b: 007\n}",
        "a: {\n    b: 1e5\n}",
        "a: {\n    b: 1.5e-2\n}",
        "a: {\n    b: 1.5f\n}",
        "a: {\n    b: 1.5F\n}",
    ],
    InvalidSeparatorError: [
        "a: {\n    b: 1,\n}",
    ],
    ScalarAtToplevelError: [
        'a: "value"',
        "a: 1",
    ],
}

_CHAR_ERROR_EXAMPLES: dict[type[DCLCharError], list[str]] = {
    InvalidFieldNameError: [
        "a: {\n    _b: 1\n}",
        "a: {\n    a__b: 1\n}",
        "a: {\n    a_: 1\n}",
        "a: {\n    a_1: 1\n}",
        "a: {\n    a-b: 1\n}",
        "a: {\n    a.b: 1\n}",
    ],
    SingleQuotesNotAllowedError: [
        "a: {\n    b: 'x'\n}",
    ],
    UnterminatedStringError: [
        'a: {\n    b: "hello\nworld"\n}',
    ],
    InvalidNumberFormatCharError: [
        "a: {\n    b: .5\n}",
        "a: {\n    b: 1.\n}",
        "a: {\n    b: +5\n}",
        "a: {\n    b: - 5\n}",
    ],
    InvalidSeparatorCharError: [
        "a: {\n    b: 1;\n}",
    ],
    TabNotAllowedError: [
        "a: {\n\tb: 1\n}",
    ],
    CarriageReturnNotAllowedError: [
        "a: {\r\n    b: 1\n}",
    ],
    AngleBracketsNotAllowedError: [
        "a: <\n    b: 1\n>",
    ],
    ByteOrderMarkError: [
        "\ufeffa: {\n    b: 1\n}",
    ],
}

_CHAR_ERRORS: dict[str, type[DCLCharError]] = {
    "'": SingleQuotesNotAllowedError,
    "\t": TabNotAllowedError,
    "\r": CarriageReturnNotAllowedError,
    "<": AngleBracketsNotAllowedError,
    ";": InvalidSeparatorCharError,
    '"': UnterminatedStringError,
    "\ufeff": ByteOrderMarkError,
    "+": InvalidNumberFormatCharError,
    "_": InvalidFieldNameError,
}

_VALUE_POSITION_CHAR_ERRORS: dict[str, type[DCLCharError]] = {
    "-": InvalidNumberFormatCharError,
    ".": InvalidNumberFormatCharError,
}

_FIELD_POSITION_CHAR_ERRORS: dict[str, type[DCLCharError]] = {
    "-": InvalidFieldNameError,
    ".": InvalidFieldNameError,
}


class Parser:
    """Parser for DCL files using Lark."""

    @cached_property
    def _parser(self) -> lark.Lark:
        return lark.Lark(_GRAMMAR_PATH.read_text(), parser="lalr", start="start")

    def _classify_char_error(
        self, e: exceptions.UnexpectedCharacters
    ) -> type[DCLCharError] | None:
        """Classify a character error using direct lookup and example matching."""
        char_class = _CHAR_ERRORS.get(e.char)
        if char_class is not None:
            return char_class

        if e.char in _VALUE_POSITION_CHAR_ERRORS:
            prev_token = e.token_history[-1] if e.token_history else None
            if prev_token is not None and prev_token.type in (
                "COLON",
                "INTEGER",
                "FLOAT",
            ):
                return _VALUE_POSITION_CHAR_ERRORS[e.char]
            return _FIELD_POSITION_CHAR_ERRORS[e.char]

        return e.match_examples(
            self._parser.parse,
            _CHAR_ERROR_EXAMPLES,
            use_accepts=True,
        )

    def _classify_token_error(
        self, e: exceptions.UnexpectedToken
    ) -> type[DCLTokenError] | None:
        """Classify a token error using pattern matching and example matching."""
        if e.token.type == "RBRACE" and e.token_history:
            prev = e.token_history[-1]
            if prev.type == "FIELD_NAME":
                val = prev.value
                if val in ("f", "d", "l") or (val[0] == "e" and val[1:].isdigit()):
                    return InvalidNumberFormatError

        return e.match_examples(
            self._parser.parse,
            _TOKEN_ERROR_EXAMPLES,
            use_accepts=True,
        )

    def parse(self, text: str) -> lark.Tree[lark.Token]:
        """Parse DCL text and return the parse tree."""
        try:
            return self._parser.parse(text)
        except exceptions.UnexpectedCharacters as e:
            exc_class = self._classify_char_error(e)
            if exc_class is not None:
                raise exc_class(e.get_context(text), e.line, e.column, e.char) from e
            raise
        except exceptions.UnexpectedToken as e:
            exc_class = self._classify_token_error(e)
            if exc_class is not None:
                raise exc_class(e.get_context(text), e.line, e.column, e.token) from e
            raise

    def parse_file(self, path: str | os.PathLike[str]) -> lark.Tree[lark.Token]:
        """Parse a DCL file and return the parse tree."""
        with open(path, encoding="utf-8", newline="") as f:
            return self.parse(f.read())
