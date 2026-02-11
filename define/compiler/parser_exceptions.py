"""Human-readable parser error messages for the Define language."""

import os
from typing import override

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

    label: str = "Syntax Error"
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

    @override
    def __str__(self) -> str:
        if self.file_path is not None:
            header = f'File "{self.file_path}", line {self.line}, column {self.column}'
        else:
            header = f"line {self.line}, column {self.column}"
        context = _escape_invisible(self.context.rstrip("\n"))
        if context:
            return f"{header}\n{context}\n{self.label}"
        return f"{header}\n{self.label}"


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


class DefineCharError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected characters."""

    char: str
    label: str

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
        self.label = f"{self.label}: {_escape_invisible(char)}"


# --- Character error subclasses ---


class ByteOrderMarkError(DefineCharError):
    """Raised when a byte order mark is present."""

    label: str = "Byte order mark not allowed"


class CarriageReturnError(DefineCharError):
    """Raised when carriage return characters are used."""

    label: str = "Carriage returns not allowed - use LF only"


class ControlCharacterError(DefineCharError):
    """Raised when control characters are used."""

    label: str = "Control characters not allowed"


class TrailingWhitespaceError(DefineCharError):
    """Raised when trailing whitespace is found."""

    label: str = "Trailing whitespace not allowed"


class UppercaseNotAllowedError(DefineCharError):
    """Raised when uppercase letters appear where not allowed."""

    label: str = "Uppercase letters not allowed here"


class InvalidCharacterError(DefineCharError):
    """Raised when an invalid character is encountered."""

    label: str = "Invalid character"


class InvalidEncodingError(DefineCharError):
    """Raised when a file contains bytes that are not valid UTF-8."""

    label: str = "Invalid UTF-8 encoding"


# --- Token error subclasses ---


class MissingBlockCloseError(DefineTokenError):
    """Raised when a closing brace is missing."""

    label: str = "Missing '}' to close block"


class MissingNewlineAfterBlockOpenError(DefineTokenError):
    """Raised when a newline is missing after an opening brace."""

    label: str = "Missing newline after '{'"


class EmptyBlockTerminatorError(DefineTokenError):
    """Raised when a definition uses an empty block instead of '.'."""

    label: str = "Empty blocks are not allowed - use '.' to end the statement"


class LocalPositionAfterTriggerError(DefineTokenError):
    """Raised when a local position definition appears after the trigger block."""

    label: str = "Local position definitions in a 'define the potential action' block must come before 'it happens when'"


class MissingActionStatementsBlockError(DefineTokenError):
    """Raised when 'and it does' is missing after the trigger conditions block."""

    label: str = "Missing 'and it does' block in this action definition"


class MissingNewlineAfterBlockCloseError(DefineTokenError):
    """Raised when a newline is missing after a closing brace."""

    label: str = "Missing newline after '}'"


class MissingTerminatorError(DefineTokenError):
    """Raised when a period or block is missing at the end of a definition."""

    label: str = "Missing '.' or '{' after definition"


class MissingNewlineError(DefineTokenError):
    """Raised when a newline is missing after a period."""

    label: str = "Missing newline after period"


class MissingOpenAngleBracketError(DefineTokenError):
    """Raised when '<' is missing before a name."""

    label: str = "Missing '<' before name"


class MissingCloseAngleBracketError(DefineTokenError):
    """Raised when '>' is missing after a name."""

    label: str = "Missing '>' after name"


class EmptyNameError(DefineTokenError):
    """Raised when a name is empty."""

    label: str = "Name cannot be empty"


class InvalidAuthorityDomainError(DefineTokenError):
    """Raised when an authority domain is invalid."""

    label: str = "Invalid authority domain"


class InvalidAuthorityPathError(DefineTokenError):
    """Raised when an authority path is invalid."""

    label: str = "Invalid authority path"


class InvalidGlobalNamePathError(DefineTokenError):
    """Raised when a global name path is invalid."""

    label: str = "Invalid global name path"


class InvalidLocalNameError(DefineTokenError):
    """Raised when a local name is invalid."""

    label: str = "Invalid local name"


class InvalidMultiverseError(DefineTokenError):
    """Raised when a multiverse name is invalid."""

    label: str = "Invalid multiverse name"


class InvalidUniverseError(DefineTokenError):
    """Raised when a universe name is invalid."""

    label: str = "Invalid universe name"


class EmptyFileError(DefineTokenError):
    """Raised when a file contains no definitions."""

    label: str = "File contains no definitions"


class IncompleteStatementError(DefineTokenError):
    """Raised when a definition is incomplete."""

    label: str = "Incomplete definition"


class UnexpectedWhitespaceError(DefineTokenError):
    """Raised when there is unexpected whitespace."""

    label: str = "Unexpected whitespace"
