"""Syntax validation for Define Configuration Language (DCL) files."""

import os
from functools import cached_property
from pathlib import Path
from typing import override

import lark
from lark import exceptions

_GRAMMAR_PATH = Path(__file__).parent.parent / "grammar.lark"


class DclSyntaxError(Exception):
    """Base class for DCL syntax errors."""

    label: str = "Syntax Error"
    context: str
    line: int
    column: int
    path_name: str | os.PathLike[str] | None

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        path_name: str | os.PathLike[str] | None = None,
    ):
        """Initialize the syntax error with location and context information."""
        super().__init__(context, line, column)
        self.context = context
        self.line = line
        self.column = column
        self.path_name = path_name


class DclTokenError(DclSyntaxError):
    """Base class for DCL syntax errors caused by unexpected tokens."""

    token: lark.Token

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        token: lark.Token,
        path_name: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the unexpected token."""
        super().__init__(context, line, column, path_name)
        self.token = token


class DclCharError(DclSyntaxError):
    """Base class for DCL syntax errors caused by unexpected characters."""

    char: str

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        char: str,
        path_name: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the unexpected character."""
        super().__init__(context, line, column, path_name)
        self.char = char


class BooleanNotSupportedError(DclTokenError):
    """Raised when true/false boolean literals are used."""

    label: str = "Boolean literals not supported - use enums instead"


class InvalidEnumCaseError(DclTokenError):
    """Raised when enum values are not ALL_CAPS."""

    label: str = "Enum values must be ALL_CAPS"


class InvalidFieldNameTokenError(DclTokenError):
    """Raised when field names don't follow naming rules (token error)."""

    label: str = "Invalid field name"


class InvalidFieldNameError(DclCharError):
    """Raised when field names don't follow naming rules (character error)."""

    label: str = "Invalid field name"


class SingleQuotesNotAllowedError(DclCharError):
    """Raised when single quotes are used instead of double quotes."""

    label: str = "Use double quotes for strings"


class UnterminatedStringError(DclCharError):
    """Raised when a string contains an unescaped newline."""

    label: str = "Unterminated string - use \\n for newlines"


class InvalidNumberFormatError(DclTokenError):
    """Raised when numbers use unsupported formats (token error)."""

    label: str = "Invalid number format"


class InvalidNumberFormatCharError(DclCharError):
    """Raised when numbers use unsupported formats (character error)."""

    label: str = "Invalid number format"


class MissingColonError(DclTokenError):
    """Raised when colon is missing between field name and value."""

    label: str = "Missing colon after field name"


class InvalidSeparatorError(DclTokenError):
    """Raised when invalid separators like comma are used (token error)."""

    label: str = "Invalid separator"


class InvalidSeparatorCharError(DclCharError):
    """Raised when invalid separators like semicolon are used (character error)."""

    label: str = "Invalid separator"


class TabNotAllowedError(DclCharError):
    """Raised when tab characters are used."""

    label: str = "Tabs not allowed - use spaces"


class CarriageReturnNotAllowedError(DclCharError):
    """Raised when carriage return characters are used."""

    label: str = "Carriage returns not allowed - use LF only"


class AngleBracketsNotAllowedError(DclCharError):
    """Raised when angle brackets are used instead of curly braces."""

    label: str = "Use curly braces {} for messages"


class ScalarAtToplevelError(DclTokenError):
    """Raised when a scalar value appears at the top level."""

    label: str = "Top-level values must be messages"


class ByteOrderMarkError(DclCharError):
    """Raised when a byte order mark is present."""

    label: str = "Byte order mark not allowed"


class MissingTrailingNewlineError(DclSyntaxError):
    """Raised when a file does not end with a newline."""

    label: str = "File does not end with a newline"

    def __init__(self, path_name: str | os.PathLike[str] | None = None):
        """Initialize with optional file name for error display."""
        super().__init__("", 0, 0, path_name)

    @override
    def __str__(self) -> str:
        """Display the exception error message."""
        if self.path_name is not None:
            return f"{os.fspath(self.path_name)}: {self.label}"
        return self.label


_TOKEN_ERROR_EXAMPLES: dict[type[DclTokenError], list[str]] = {
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

_CHAR_ERROR_EXAMPLES: dict[type[DclCharError], list[str]] = {
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

_CHAR_ERRORS: dict[str, type[DclCharError]] = {
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

_VALUE_POSITION_CHAR_ERRORS: dict[str, type[DclCharError]] = {
    "-": InvalidNumberFormatCharError,
    ".": InvalidNumberFormatCharError,
}

_FIELD_POSITION_CHAR_ERRORS: dict[str, type[DclCharError]] = {
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
    ) -> type[DclCharError] | None:
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
    ) -> type[DclTokenError] | None:
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

    def parse(
        self, text: str, path_name: str | os.PathLike[str] | None = None
    ) -> lark.Tree[lark.Token]:
        """Parse DCL text and return the parse tree.

        path_name is only used for error messages.
        """
        try:
            tree = self._parser.parse(text)
            if text and text[-1] != "\n":
                raise MissingTrailingNewlineError(path_name)
        except exceptions.UnexpectedCharacters as e:
            exc_class = self._classify_char_error(e)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(text), e.line, e.column, e.char, path_name
                ) from e
            raise
        except exceptions.UnexpectedToken as e:
            exc_class = self._classify_token_error(e)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(text), e.line, e.column, e.token, path_name
                ) from e
            raise
        return tree

    def parse_file(self, path: str | os.PathLike[str]) -> lark.Tree[lark.Token]:
        """Parse a DCL file and return the parse tree."""
        with open(path, encoding="utf-8", newline="") as f:
            return self.parse(f.read(), path_name=path)
