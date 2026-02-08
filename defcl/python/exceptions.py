"""DCL syntax errors."""

import os
from typing import override

import lark


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
