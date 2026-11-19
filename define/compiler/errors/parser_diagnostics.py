"""Diagnostics that the parser reports."""

from __future__ import annotations

from typing import ClassVar

from define.compiler.errors import diagnostics, invisible_characters


class ByteOrderMarkInCommentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a UTF-8 byte order mark in a comment."""

    message_format: ClassVar[str] = (
        "comments may not have a UTF-8 byte order mark (U+FEFF)"
    )


class ControlCharacterInCommentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a control character in a comment."""

    escaped_character: str
    message_format: ClassVar[str] = (
        "comments may not have the control character {self.escaped_character}"
    )


class IncorrectIndentationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a line has incorrect indentation."""

    expected_indent: int
    actual_indent: int
    message_format: ClassVar[str] = (
        "expected {self.expected_indent} spaces of indentation on this line,"
        " but found {self.actual_indent}"
    )


class InvisibleCharacterInCommentDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an invisible character in a comment that the Invisible Characters rule does not allow there."""

    character: str
    message_format: ClassVar[str] = (
        "comments may not have the invisible character {self.description}"
    )

    @property
    def description(self) -> str:
        """The character's code point and, when Unicode names it, its name."""
        return invisible_characters.describe_invisible_character(self.character)


class MissingNewlineAtEndOfFileDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a source file that does not end with a line feed."""

    message_format: ClassVar[str] = "Define source files must end with a newline"


class MissingSpaceBeforeCommentAfterBraceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a comment directly after a '{' or '}'."""

    message_format: ClassVar[str] = (
        "a comment after '{{' or '}}' must have a space before its '#'"
    )


class MissingSpaceBeforeCommentAfterTerminatorDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a comment directly after a statement's '.'."""

    message_format: ClassVar[str] = (
        "a comment after a statement's '.' must have a space before its '#'"
    )


class MissingTerminatorAtEndOfLineDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a statement whose line ends where its '.' belongs."""

    message_format: ClassVar[str] = "this statement must end with a '.'"


class SpaceBeforeOpenAngleBracketDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for spaces between a name type and the '<' of its name."""

    message_format: ClassVar[str] = (
        "a name type and the '<' of its name may not have spaces between them"
    )


class TrailingWhitespaceDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for spaces at the end of a line."""

    message_format: ClassVar[str] = "lines may not end with spaces"
