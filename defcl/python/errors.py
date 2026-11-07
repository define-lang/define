"""The errors that validating a DCL file raises and reports."""

from __future__ import annotations

import typing

import msgspec

if typing.TYPE_CHECKING:
    from defcl.python import error_types


class SourceLocation(msgspec.Struct, frozen=True, gc=False):
    """The part of a DCL file that an error covers.

    Lines and columns are 1-based, and columns count characters. ``end_line``
    and ``end_column`` are the position of the last character that the
    location covers.
    """

    line: int
    column: int
    end_line: int
    end_column: int


class DclError(Exception):
    """The first syntax error in a DCL file.

    Its string is its location, as its source line underlined with carets,
    then its message.
    """

    kind: error_types.DclErrorKind
    message: str
    location: SourceLocation

    def __init__(
        self,
        kind: error_types.DclErrorKind,
        message: str,
        location: SourceLocation,
        rendered: str,
    ):
        """Initialize the error with its message, which does not include its location, and its rendered text."""
        super().__init__(rendered)
        self.kind = kind
        self.message = message
        self.location = location


class UnexpectedCharacterError(DclError):
    """An UNEXPECTED_CHARACTER error: a character that DCL does not allow."""

    character: str

    def __init__(
        self,
        kind: error_types.DclErrorKind,
        message: str,
        location: SourceLocation,
        rendered: str,
        character: str,
    ):
        """Initialize the error with the character that DCL does not allow."""
        super().__init__(kind, message, location, rendered)
        self.character = character


class InvalidSchemaError(Exception):
    """A descriptor set that DCL files cannot be checked against."""


class DclDiagnostic(msgspec.Struct, frozen=True):
    """An error that checking a DCL file against its schema found."""

    kind: error_types.DiagnosticKind
    # The diagnostic's message, without its location.
    message: str
    location: SourceLocation
    field_name: str
    # The diagnostic's location, as its source line underlined with carets, then
    # its message.
    rendered: str

    @typing.override
    def __str__(self) -> str:
        return self.rendered


class UnknownFieldNameDiagnostic(DclDiagnostic, frozen=True):
    """An UNKNOWN_FIELD_NAME diagnostic: a field name that its message type has no field for."""

    # The full name of the message type that has no field named field_name.
    message_type: str


class UnknownEnumValueDiagnostic(DclDiagnostic, frozen=True):
    """An UNKNOWN_ENUM_VALUE diagnostic: an enum value whose name its field's enum type has no value for."""

    # The full name of the enum type that has no value with the enum value's
    # name.
    enum_type: str
