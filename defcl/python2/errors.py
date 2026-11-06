"""The errors that validating a DCL file raises and reports."""

from __future__ import annotations

import typing

import msgspec

if typing.TYPE_CHECKING:
    from defcl.python2 import error_types


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
    # The character that DCL does not allow, for an UNEXPECTED_CHARACTER error.
    character: str | None

    def __init__(
        self,
        kind: error_types.DclErrorKind,
        message: str,
        location: SourceLocation,
        character: str | None,
        rendered: str,
    ):
        """Initialize the error with its message, which does not include its location, and its rendered text."""
        super().__init__(rendered)
        self.kind = kind
        self.message = message
        self.location = location
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
    # The full name of the message type that has no field named field_name, for
    # an UNKNOWN_FIELD_NAME diagnostic.
    message_type: str | None
    # The diagnostic's location, as its source line underlined with carets, then
    # its message.
    rendered: str
