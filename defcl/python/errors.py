"""The diagnostics that validating a DCL file reports, and the errors that it raises."""

from __future__ import annotations

import typing

import msgspec

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from defcl.python import error_types


class InvalidSchemaError(Exception):
    """A descriptor set that DCL files cannot be checked against."""


class DclDiagnostic(msgspec.Struct, frozen=True):
    """An error in a DCL file."""

    # The diagnostic's message, without its location.
    message: str
    # None when the diagnostic is about the whole file.
    location: rendering.SourceLocation | None
    # The file that the diagnostic is in, or None for text that is not from a
    # file.
    file_path: str | None

    def format(self, sources: rendering.SourceMap) -> str:
        """Format the diagnostic: its location, with its source line underlined with carets, or else its file, then its message."""
        if self.location is not None:
            return f"{sources.render_location(self.location)}\n{self.message}"
        if self.file_path is not None:
            return f"{sources.render_header_without_position(self.file_path)}\n{self.message}"
        return self.message


class SyntaxDiagnostic(DclDiagnostic, frozen=True):
    """A syntax error in a file. Each error in the file's layout is reported; any other syntax error stops the checks of the file."""

    kind: error_types.SyntaxDiagnosticKind


class UnexpectedCharacterDiagnostic(SyntaxDiagnostic, frozen=True):
    """An UNEXPECTED_CHARACTER diagnostic: a character that DCL does not allow."""

    character: str


class ControlCharacterDiagnostic(SyntaxDiagnostic, frozen=True):
    """A CONTROL_CHARACTER diagnostic: a control character in a comment or a string."""

    character: str


class InvisibleCharacterDiagnostic(SyntaxDiagnostic, frozen=True):
    """An INVISIBLE_CHARACTER diagnostic: an invisible character that the Invisible Characters rule does not allow in a comment or a string."""

    character: str


class InvalidEncodingDiagnostic(SyntaxDiagnostic, frozen=True):
    """An INVALID_ENCODING diagnostic: a byte that does not start a valid UTF-8 character."""

    byte: int


class WrongIndentationDiagnostic(SyntaxDiagnostic, frozen=True):
    """A WRONG_INDENTATION diagnostic: a line that does not start with the spaces of its indentation."""

    expected_spaces: int


class SemanticDiagnostic(DclDiagnostic, frozen=True):
    """An error that checking a DCL file against its schema found."""

    kind: error_types.SemanticDiagnosticKind
    field_name: str


class UnknownFieldNameDiagnostic(SemanticDiagnostic, frozen=True):
    """An UNKNOWN_FIELD_NAME diagnostic: a field name that its message type has no field for."""

    # The full name of the message type that has no field named field_name.
    message_type: str


class UnknownEnumValueDiagnostic(SemanticDiagnostic, frozen=True):
    """An UNKNOWN_ENUM_VALUE diagnostic: an enum value whose name its field's enum type has no value for."""

    # The full name of the enum type that has no value with the enum value's
    # name.
    enum_type: str


class IntegerOutOfRangeDiagnostic(SemanticDiagnostic, frozen=True):
    """An INTEGER_OUT_OF_RANGE diagnostic: an integer outside the range of its field's type."""

    # The field's type, such as "uint32".
    field_type: str


class FloatOutOfRangeDiagnostic(SemanticDiagnostic, frozen=True):
    """A FLOAT_OUT_OF_RANGE diagnostic: a number too large in magnitude for its field's type."""

    # The field's type, "float" or "double".
    field_type: str


class SecondFieldOfOneofDiagnostic(SemanticDiagnostic, frozen=True):
    """A SECOND_FIELD_OF_ONEOF diagnostic: a field of a oneof that its message value already has another field of."""

    # The oneof's full name: its message type's full name, then its own name.
    oneof: str


class FieldOutOfOrderDiagnostic(SemanticDiagnostic, frozen=True):
    """A FIELD_OUT_OF_ORDER diagnostic: a field written after a field with a higher field number."""

    # The name of the field with the highest field number that is written
    # before field_name.
    later_field: str
