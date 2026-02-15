"""Human-readable parser error messages for the Define language."""

import os
from typing import ClassVar, Self, override

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
        file_path: str | os.PathLike[str] | None,
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
        exception: lark.exceptions.UnexpectedToken,
        source: str,
        file_path: str | os.PathLike[str] | None,
    ):
        """Initialize with the unexpected token."""
        super().__init__(
            exception.get_context(source),
            exception.line,
            exception.column,
            file_path,
        )
        self.token = exception.token


class DefineCharError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected characters."""

    char: str

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        char: str,
        file_path: str | os.PathLike[str] | None,
    ):
        """Initialize with the unexpected character."""
        super().__init__(context, line, column, file_path)
        self.char = char

    @classmethod
    def from_lark_exception(
        cls,
        exception: lark.exceptions.UnexpectedInput,
        source: str,
        char: str,
        file_path: str | os.PathLike[str] | None,
    ) -> Self:
        """Construct a character error from a Lark exception."""
        return cls(
            exception.get_context(source),
            exception.line,
            exception.column,
            char,
            file_path,
        )

    @property
    def escaped_char(self) -> str:
        """Return the character in a readable escaped form."""
        return _escape_invisible(self.char)

    @override
    def _message_fields(self) -> dict[str, object]:
        fields = super()._message_fields()
        fields["escaped_char"] = self.escaped_char
        return fields


class DefineNameSyntaxError(DefineSyntaxError):
    """Base class for Define syntax errors from parsing name content."""


# --- Character error subclasses ---


class ByteOrderMarkError(DefineCharError):
    """Raised when a byte order mark is present."""

    message_format: ClassVar[str] = (
        "UTF-8 Byte Order Marks ({escaped_char}) are not allowed in Define source code files."
    )


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

    message_format: ClassVar[str] = "Trailing whitespace is not allowed."


class InvalidCharacterError(DefineCharError):
    """Raised when an invalid character is encountered."""

    message_format: ClassVar[str] = (
        "Character ({escaped_char}) is not valid at this location in Define syntax."
    )


class InvalidEncodingError(DefineCharError):
    """Raised when a file contains bytes that are not valid UTF-8."""

    message_format: ClassVar[str] = "Invalid UTF-8 byte sequence: ({escaped_char})."


# --- Token error subclasses ---

# The token error subclasses don't use the suffix "Error." Instead, they are expressed
# as the name of the problem. This is much more intuitive to type and read in the
# parser error classification system.
#
# Keep these in alphabetical order.


class EmptyBlock(DefineTokenError):
    """Wrote {}."""

    message_format: ClassVar[str] = (
        "Blocks cannot be empty. Instead, use a period (.) to terminate the statement."
    )


class EmptyName(DefineTokenError):
    """Saw a <> in a name."""

    message_format: ClassVar[str] = "Name cannot be empty."


class ExpectedGlobalDefinition(DefineTokenError):
    """Thrown when the parser expected to see a global definition and didn't see one."""

    message_format: ClassVar[str] = (
        "Expected a global definition like 'define the potential ...'"
    )


class ExtraWhitespace(DefineTokenError):
    """When you write two spaces where you should have written one."""

    message_format: ClassVar[str] = (
        "Line looks like it contains too many spaces between words."
        + " All words in Define require exactly one space between them."
    )


class GlobalDefinitionInLocalContext(DefineTokenError):
    """Trying to do 'define the potential' where you should just do 'define the'."""

    message_format: ClassVar[str] = (
        "Global definition not allowed in a local scope. Write 'define the' instead of 'define the potential'."
    )


class InvalidActionStatementsBlock(DefineTokenError):
    """Nonsense in an Action Statements Block."""

    message_format: ClassVar[str] = "Not a valid action statement or local definition."


class InvalidActionDefinitionsBlock(DefineTokenError):
    """Wrote something totally invalid in an Action Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a potential action definition."


class InvalidPositionConstraintBlock(DefineTokenError):
    """Write something nonsensical in a position constraint block."""

    message_format: ClassVar[str] = "Invalid syntax in a position constraint block."


class InvalidPositionDefinitionBlock(DefineTokenError):
    """Write something nonsensical in a Position Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a position definition."


class InvalidPositionDefinitionLocationInAction(DefineTokenError):
    """Wrote 'define the position' after the action statements block."""

    message_format: ClassVar[str] = (
        "'define the position' statements in an action must go above the 'it happens when' block."
    )


class MissingActionDefinitionSyntax(DefineTokenError):
    """Forgot to write 'it happens when' in an Action Definition Block."""

    message_format: ClassVar[str] = (
        "Action definition is missing an 'it happens when' block."
    )


class MissingActionStatementsBlock(DefineTokenError):
    """Forgot the 'and it does' in an Action Definition Block."""

    message_format: ClassVar[str] = "Missing 'and it does' in this action definition."


class MissingCloseAngleBracket(DefineTokenError):
    """A missing > on a name."""

    name: str
    message_format: ClassVar[str] = "Missing '>' on this name: {name}"

    def __init__(
        self,
        exception: lark.exceptions.UnexpectedToken,
        source: str,
        file_path: str | os.PathLike[str] | None,
        name: str,
    ):
        """Initialize with the parsed name token that missed '>'."""
        super().__init__(exception, source, file_path)
        self.name = name


class MissingCloseBrace(DefineTokenError):
    """Forgot to write } at the end of a block."""

    message_format: ClassVar[str] = "Missing a closing '}}' somewhere in this block."


class MissingNewlineAfterCloseBrace(DefineTokenError):
    """Forgot the newline after }."""

    message_format: ClassVar[str] = "Missing newline after '}}'"


class MissingNewlineAfterOpenBrace(DefineTokenError):
    """Forgot the newline after {."""

    message_format: ClassVar[str] = "Missing newline after '{{'"


class MissingNewlineAfterTerminator(DefineTokenError):
    """Didn't see a newline after ."""

    message_format: ClassVar[str] = "Missing newline after statement terminator."


class MissingNewlineAtEof(DefineTokenError):
    """Hitting an EOF without a newline before it."""

    message_format: ClassVar[str] = "Define source code files must end with a newline."


class MissingOpenAngleBracket(DefineTokenError):
    """A missing < on a name (could be just a raw "define the position", too)."""

    name: str
    message_format: ClassVar[str] = "Missing '<' at the start of a name: {name}"

    def __init__(
        self,
        exception: lark.exceptions.UnexpectedToken,
        source: str,
        file_path: str | os.PathLike[str] | None,
        name: str,
    ):
        """Initialize with the parsed name token that missed '<'."""
        super().__init__(exception, source, file_path)
        self.name = name


class MissingOpenBrace(DefineTokenError):
    """Forgot the { in a situation where only that is valid."""

    message_format: ClassVar[str] = (
        "This line must end with a single space followed by a '{{'."
    )


class MissingPositionConstraintContent(DefineTokenError):
    """Left out syntax from a position constraint block."""

    message_format: ClassVar[str] = (
        "Position constraint blocks must contain at least one 'it has the' statement."
    )


class MissingPositionDefinitionContent(DefineTokenError):
    """Left out mandatory content from a position definition block."""

    message_format: ClassVar[str] = (
        "Position definition blocks must contain at least a 'it may only contain the dimension points where' block."
        + " If you want an empty position definition, end it with a period (.) instead of a block ({{}})."
    )


class MissingTerminator(DefineTokenError):
    """Forgot . or {."""

    message_format: ClassVar[str] = (
        "Statements must end with a '.' or a single space followed by '{{'"
    )


class MissingWhitespaceBeforeBrace(DefineTokenError):
    """Forgot to put a space before {."""

    message_format: ClassVar[str] = "Missing a space before '{{'"


# --- Name syntax errors ---


class GlobalNameDefinitionRequiresFqun(DefineNameSyntaxError):
    """Raised when a global definition uses short-form '/path'."""

    message_format: ClassVar[str] = (
        "Global name definitions must use a fully qualified universe name. "
        "Replace short-form paths with '<...:/path>'."
    )


class GlobalNameInvalidFqunFormat(DefineNameSyntaxError):
    """Raised when a fully-qualified universe name has invalid parts."""

    message_format: ClassVar[str] = (
        "Fully qualified universe name format is invalid. "
        "Use '<multiverse:authority:universe:/path>' or "
        "'<authority:universe:/path>' or '<standard:/path>'."
    )
