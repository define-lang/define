"""DCL syntax errors."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

if TYPE_CHECKING:
    import os

    from defcl.python.lark import lark_standalone


class DclSyntaxError(Exception):
    """Base class for DCL syntax errors."""

    label_format: ClassVar[str] = "Syntax Error"
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

    @property
    def label(self) -> str:
        """Render the label from the format template."""
        return self.label_format.format(self=self)

    @override
    def __str__(self) -> str:
        if self.path_name is not None:
            header = f'File "{self.path_name}", line {self.line}, column {self.column}'
        else:
            header = f"line {self.line}, column {self.column}"
        context = self.context.rstrip("\n")
        if context:
            return f"{header}\n{context}\n{self.label}"
        return f"{header}\n{self.label}"


class DclTokenError(DclSyntaxError):
    """Base class for DCL syntax errors caused by unexpected tokens."""

    token: lark_standalone.Token

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        token: lark_standalone.Token,
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

    label_format: ClassVar[str] = "Boolean literals not supported - use enums instead"


class InvalidEnumCaseError(DclTokenError):
    """Raised when enum values are not ALL_CAPS."""

    label_format: ClassVar[str] = "Enum values must be ALL_CAPS"


class InvalidFieldNameTokenError(DclTokenError):
    """Raised when field names don't follow naming rules (token error)."""

    label_format: ClassVar[str] = "Invalid field name"


class InvalidFieldNameError(DclCharError):
    """Raised when field names don't follow naming rules (character error)."""

    label_format: ClassVar[str] = "Invalid field name"


class SingleQuotesNotAllowedError(DclCharError):
    """Raised when single quotes are used instead of double quotes."""

    label_format: ClassVar[str] = "Use double quotes for strings"


class UnterminatedStringError(DclCharError):
    """Raised when a string contains an unescaped newline."""

    label_format: ClassVar[str] = "Unterminated string - use \\n for newlines"


class InvalidNumberFormatError(DclTokenError):
    """Raised when numbers use unsupported formats (token error)."""

    label_format: ClassVar[str] = "Invalid number format"


class InvalidNumberFormatCharError(DclCharError):
    """Raised when numbers use unsupported formats (character error)."""

    label_format: ClassVar[str] = "Invalid number format"


class MissingColonError(DclTokenError):
    """Raised when colon is missing between field name and value."""

    label_format: ClassVar[str] = "Missing colon after field name"


class InvalidSeparatorError(DclTokenError):
    """Raised when invalid separators like comma are used (token error)."""

    label_format: ClassVar[str] = "Invalid separator"


class InvalidSeparatorCharError(DclCharError):
    """Raised when invalid separators like semicolon are used (character error)."""

    label_format: ClassVar[str] = "Invalid separator"


class TabNotAllowedError(DclCharError):
    """Raised when tab characters are used."""

    label_format: ClassVar[str] = "Tabs not allowed - use spaces"


class CarriageReturnNotAllowedError(DclCharError):
    """Raised when carriage return characters are used."""

    label_format: ClassVar[str] = "Carriage returns not allowed - use LF only"


class AngleBracketsNotAllowedError(DclCharError):
    """Raised when angle brackets are used instead of curly braces."""

    label_format: ClassVar[str] = "Use curly braces {{}} for messages"


class ScalarAtToplevelError(DclTokenError):
    """Raised when a scalar value appears at the top level."""

    label_format: ClassVar[str] = "Top-level values must be messages"


class ByteOrderMarkError(DclCharError):
    """Raised when a byte order mark is present."""

    label_format: ClassVar[str] = "Byte order mark not allowed"


class IntegerEnumError(DclSyntaxError):
    """Raised when an integer value is used for an enum field."""

    label_format: ClassVar[str] = (
        "{self.field_name}: Integer enum values are not allowed"
    )
    field_name: str

    def __init__(
        self,
        line: int,
        column: int,
        field_name: str,
        path_name: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the field name that has an integer enum value."""
        super().__init__("", line, column, path_name)
        self.field_name = field_name


class RepeatedFieldWithoutBracketsError(DclSyntaxError):
    """Raised when a repeated field value does not use bracket syntax."""

    label_format: ClassVar[str] = (
        "{self.field_name}: Repeated fields must use bracket [] syntax"
    )
    field_name: str

    def __init__(
        self,
        line: int,
        column: int,
        field_name: str,
        path_name: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the field name missing bracket syntax."""
        super().__init__("", line, column, path_name)
        self.field_name = field_name


class MissingTrailingNewlineError(DclSyntaxError):
    """Raised when a file does not end with a newline."""

    label_format: ClassVar[str] = "File does not end with a newline"

    def __init__(self, path_name: str | os.PathLike[str] | None = None):
        """Initialize with optional file name for error display."""
        super().__init__("", 0, 0, path_name)

    @override
    def __str__(self) -> str:
        if self.path_name is not None:
            return f'File "{self.path_name}"\n{self.label}'
        return self.label
