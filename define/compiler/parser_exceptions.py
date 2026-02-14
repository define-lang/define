"""Human-readable parser error messages for the Define language."""

import os
from typing import ClassVar, override

import lark


def _escape_invisible(text: str) -> str:
    """Replace non-printable characters with their Python escape sequences."""
    chars: list[str] = []
    for c in text:
        if c == "\n" or c.isprintable():
            chars.append(c)
        else:
            chars.append(repr(c)[1:-1])
    return "".join(chars)


class DefineSyntaxError(Exception):
    """Base class for Define syntax errors."""

    message_format: ClassVar[str] = "Syntax error."
    context: str
    line: int
    column: int
    file_path: str | os.PathLike[str] | None

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        file_path: str | os.PathLike[str] | None = None,
    ):
        """Initialize the syntax error with location and context information."""
        super().__init__(context, line, column)
        self.context = context
        self.line = line
        self.column = column
        self.file_path = file_path

    def _message_fields(self) -> dict[str, object]:
        """Return fields available for message formatting."""
        return dict(self.__dict__)

    @property
    def message(self) -> str:
        """Render the error message from the format template."""
        return self.message_format.format(**self._message_fields())

    @override
    def __str__(self) -> str:
        if self.file_path is not None:
            header = f'File "{self.file_path}", line {self.line}, column {self.column}'
        else:
            header = f"line {self.line}, column {self.column}"
        context = _escape_invisible(self.context.rstrip("\n"))
        if context:
            return f"{header}\n{context}\n{self.message}"
        return f"{header}\n{self.message}"


class DefineTokenError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected tokens."""

    token: lark.Token

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        token: lark.Token,
        file_path: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the unexpected token."""
        super().__init__(context, line, column, file_path)
        self.token = token

    @property
    def token_description(self) -> str:
        """Return a readable description of the unexpected token."""
        text = str(self.token)
        if self.token.type == "$END":
            return "the end of the file"
        if text == "\n":
            return "a newline"
        if text.strip() == "":
            return "whitespace"
        return f"'{_escape_invisible(text)}'"

    @override
    def _message_fields(self) -> dict[str, object]:
        fields = super()._message_fields()
        fields["token_description"] = self.token_description
        return fields


class DefineCharError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected characters."""

    char: str

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        char: str,
        file_path: str | os.PathLike[str] | None = None,
    ):
        """Initialize with the unexpected character."""
        super().__init__(context, line, column, file_path)
        self.char = char

    @property
    def escaped_char(self) -> str:
        """Return the character in a readable escaped form."""
        return _escape_invisible(self.char)

    @override
    def _message_fields(self) -> dict[str, object]:
        fields = super()._message_fields()
        fields["escaped_char"] = self.escaped_char
        return fields


class DefineNameSyntaxError(DefineTokenError):
    """Base class for Define syntax errors from parsing name content."""


# --- Character error subclasses ---


class ByteOrderMarkError(DefineCharError):
    """Raised when a byte order mark is present."""

    message_format: ClassVar[str] = "Unexpected byte order mark ({escaped_char})."


class CarriageReturnError(DefineCharError):
    """Raised when carriage return characters are used."""

    message_format: ClassVar[str] = (
        "Carriage return character ({escaped_char}) is not allowed."
    )


class ControlCharacterError(DefineCharError):
    """Raised when control characters are used."""

    message_format: ClassVar[str] = "Control character ({escaped_char}) is not allowed."


class TrailingWhitespaceError(DefineCharError):
    """Raised when trailing whitespace is found."""

    message_format: ClassVar[str] = (
        "Trailing whitespace ({escaped_char}) is not allowed."
    )


class InvalidCharacterError(DefineCharError):
    """Raised when an invalid character is encountered."""

    message_format: ClassVar[str] = (
        "Character ({escaped_char}) is not valid at this location in Define syntax."
    )


class InvalidEncodingError(DefineCharError):
    """Raised when a file contains bytes that are not valid UTF-8."""

    message_format: ClassVar[str] = "Invalid UTF-8 content ({escaped_char}) was found."


# --- Token error subclasses ---


class MissingBlockCloseError(DefineTokenError):
    """Raised when a closing brace is missing."""

    message_format: ClassVar[str] = "Missing '}}' to close block."


class MissingNewlineAfterBlockOpenError(DefineTokenError):
    """Raised when a newline is missing after an opening brace."""

    message_format: ClassVar[str] = "Expected a newline after '{{'."


class EmptyBlockTerminatorError(DefineTokenError):
    """Raised when a definition uses an empty block instead of '.'."""

    message_format: ClassVar[str] = (
        "Empty blocks are not allowed for definitions. Use '.' to end the definition."
    )


class LocalPositionAfterTriggerError(DefineTokenError):
    """Raised when a local position definition appears after the trigger block."""

    message_format: ClassVar[str] = (
        "Local position definitions must appear before 'it happens when' "
        "in an action block."
    )


class GlobalPositionInLocalScopeError(DefineTokenError):
    """Raised when a global position definition appears in a local scope."""

    message_format: ClassVar[str] = (
        "Global position definitions are not allowed in local scopes. "
        "Use 'define the position<...>' for local positions."
    )


class MissingActionStatementsBlockError(DefineTokenError):
    """Raised when 'and it does' is missing after the trigger conditions block."""

    message_format: ClassVar[str] = (
        "Action definitions require an 'and it does' block after 'it happens when'."
    )


class MissingNewlineAfterBlockCloseError(DefineTokenError):
    """Raised when a newline is missing after a closing brace."""

    message_format: ClassVar[str] = "Expected a newline after '}}'."


class MissingTerminatorError(DefineTokenError):
    """Raised when a period or block is missing at the end of a definition."""

    message_format: ClassVar[str] = "Definition is missing a terminator ('.' or '{{')."


class MissingNewlineError(DefineTokenError):
    """Raised when a newline is missing after a period."""

    message_format: ClassVar[str] = "Expected a newline after '.'."


class MissingOpenAngleBracketError(DefineTokenError):
    """Raised when '<' is missing before a name."""

    message_format: ClassVar[str] = "Expected '<' before the name."


class MissingCloseAngleBracketError(DefineTokenError):
    """Raised when '>' is missing after a name."""

    message_format: ClassVar[str] = "Expected '>' after the name."


class EmptyNameError(DefineTokenError):
    """Raised when a name is empty."""

    message_format: ClassVar[str] = "Name cannot be empty."


class EmptyFileError(DefineTokenError):
    """Raised when a file contains no definitions."""

    message_format: ClassVar[str] = (
        "File has no definitions. Add at least one 'define the potential ...' line."
    )


class IncompleteStatementError(DefineTokenError):
    """Raised when a definition is incomplete."""

    message_format: ClassVar[str] = "This definition is incomplete."


class MultiplePositionConstraintBlocksError(DefineTokenError):
    """Raised when a position definition contains more than one constraints block."""

    message_format: ClassVar[str] = (
        "Only one 'it may only contain dimension points where' block "
        "is allowed per position definition."
    )


class UnexpectedWhitespaceError(DefineTokenError):
    """Raised when there is unexpected whitespace."""

    message_format: ClassVar[str] = "Unexpected whitespace near {token_description}."


class InvalidGlobalNameSyntaxError(DefineNameSyntaxError):
    """Raised when a global name has invalid structural syntax."""

    message_format: ClassVar[str] = (
        "Global name syntax is invalid at {token_description}."
    )


class GlobalNameDefinitionRequiresFqunError(InvalidGlobalNameSyntaxError):
    """Raised when a global definition uses short-form '/path'."""

    message_format: ClassVar[str] = (
        "Global name definitions must use a fully qualified universe name. "
        "Replace short-form paths with '<...:/path>'."
    )


class GlobalNameInvalidFqunFormatError(InvalidGlobalNameSyntaxError):
    """Raised when a fully-qualified universe name has invalid parts."""

    message_format: ClassVar[str] = (
        "Fully qualified universe name format is invalid. "
        "Use '<multiverse:authority:universe:/path>' or "
        "'<authority:universe:/path>' or '<standard:/path>'."
    )
