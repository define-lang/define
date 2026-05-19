"""Human-readable parser error messages for the Define language."""

import pathlib
from typing import ClassVar, Self, override

from define.compiler import exceptions
from define.compiler.lark import lark_standalone


def _escape_invisible(text: str) -> str:
    """Replace non-printable characters with their Python escape sequences."""
    chars: list[str] = []
    for c in text:
        if c == "\n" or c.isprintable():
            chars.append(c)
        else:
            chars.append(repr(c)[1:-1])
    return "".join(chars)


class DefineSyntaxError(exceptions.DefineError):
    """Base class for Define syntax errors."""

    message_format: ClassVar[str] = "Syntax error."
    context: str
    line: int
    column: int
    file_path: pathlib.PurePosixPath | None

    def __init__(
        self,
        context: str,
        line: int,
        column: int,
        file_path: pathlib.PurePosixPath | None,
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

    token: lark_standalone.Token

    def __init__(
        self,
        exception: lark_standalone.UnexpectedToken,
        source: str,
        file_path: pathlib.PurePosixPath | None,
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
        file_path: pathlib.PurePosixPath | None,
    ):
        """Initialize with the unexpected character."""
        super().__init__(context, line, column, file_path)
        self.char = char

    @classmethod
    def from_lark_exception(
        cls,
        exception: lark_standalone.UnexpectedInput,
        source: str,
        char: str,
        file_path: pathlib.PurePosixPath | None,
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


class InvalidLocalNameCharacter(DefineCharError):
    """Wrote something invalid where only a local name is accepted."""

    message_format: ClassVar[str] = "'{escaped_char}' is not allowed in local names."


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


class ExpectedChainSeparatorOrTerminator(DefineTokenError):
    """Wrote something wrong where we expect :: or the end of a statement."""

    message_format: ClassVar[str] = "Expected '::' or '.' here."


class ExpectedGlobalDefinition(DefineTokenError):
    """Thrown when the parser expected to see a global definition and didn't see one."""

    message_format: ClassVar[str] = (
        "Expected a global definition like 'define the potential ...'"
    )


class ExpectedNameType(DefineTokenError):
    """Expected a typed reference kind."""

    message_format: ClassVar[str] = "Expected 'position' or 'action'."


class ExtraWhitespace(DefineTokenError):
    """When you write two spaces where you should have written one."""

    message_format: ClassVar[str] = (
        "Line looks like it contains too many spaces between words."
        + " All words in Define require exactly one space between them."
    )


class GlobalPositionDefinitionInLocalContext(DefineTokenError):
    """Wrote 'define the potential position' where only 'define the position' is accepted."""

    message_format: ClassVar[str] = (
        "Global position definition not allowed here."
        " Write 'define the position' instead of 'define the potential position'."
    )


class InvalidActionStatementsBlock(DefineTokenError):
    """Nonsense in an Action Statements Block."""

    message_format: ClassVar[str] = "Not a valid action statement or local definition."


class InvalidActionDefinitionsBlock(DefineTokenError):
    """Wrote something totally invalid in an Action Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a potential action definition."


class InvalidMoveStatementSyntax(DefineTokenError):
    """Expected ' to ' or '::' after a position reference in a move statement."""

    message_format: ClassVar[str] = (
        "The syntax for a move statement looks like:"
        " move the dimension point in position<foo> to position<bar>."
        " Expected a 'to' or a longer chained name (a '::' followed by another name) here."
    )


class InvalidPositionConstraintBlock(DefineTokenError):
    """Write something nonsensical in a position constraint block."""

    message_format: ClassVar[str] = "Invalid syntax in a position constraint block."


class InvalidTriggerConditionsBlock(DefineTokenError):
    """Nonsense in a Trigger Conditions Block."""

    message_format: ClassVar[str] = "Not a valid trigger condition statement."


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
        exception: lark_standalone.UnexpectedToken,
        source: str,
        file_path: pathlib.PurePosixPath | None,
        name: str,
    ):
        """Initialize with the parsed name token that missed '>'."""
        super().__init__(exception, source, file_path)
        self.name = name


class MissingCloseBrace(DefineTokenError):
    """Forgot to write } at the end of a block."""

    message_format: ClassVar[str] = "Missing a closing '}}' somewhere in this block."


class InvalidHasADimensionPointSyntax(DefineTokenError):
    """Expected ' has a dimension point' after a local name in a trigger condition."""

    message_format: ClassVar[str] = (
        "The syntax for a dimension point presence check looks like:"
        " the position<foo> has a dimension point."
        " Expected ' has a dimension point' here."
    )


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
        exception: lark_standalone.UnexpectedToken,
        source: str,
        file_path: pathlib.PurePosixPath | None,
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


class MissingPotentialPositionDefinitionContent(DefineTokenError):
    """Left out mandatory content from a potential position definition block."""

    message_format: ClassVar[str] = (
        "Potential position definition blocks must contain an"
        " 'it may only contain dimension points where' block"
        " and/or an 'after it is assigned' block."
        " If you want an empty position definition, end it with a period (.) instead of a block ({{}})."
    )


class InvalidPotentialPositionDefinitionBlock(DefineTokenError):
    """Write something nonsensical in a Potential Position Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a potential position definition."


class MissingTerminator(DefineTokenError):
    """Forgot ."""

    message_format: ClassVar[str] = "This statement must end with a '.'."


class MissingTriggerConditionContent(DefineTokenError):
    """Left out content from a trigger conditions block."""

    message_format: ClassVar[str] = (
        "Trigger conditions blocks must contain at least one 'the ... has a dimension point.' statement."
    )


class MissingTerminatorOrBrace(DefineTokenError):
    """Forgot . or {."""

    message_format: ClassVar[str] = (
        "This statement must end with a '.' or a single space followed by '{{'"
    )


class MissingWhitespace(DefineTokenError):
    """Forgot required whitespace."""

    message_format: ClassVar[str] = "Missing a space."


class MissingWhitespaceBeforeBrace(DefineTokenError):
    """Forgot to put a space before {."""

    message_format: ClassVar[str] = "Missing a space before '{{'"


class QualityImplicationInWrongLocation(DefineTokenError):
    """Wrote an 'it also assigns the' statement somewhere it isn't allowed."""

    message_format: ClassVar[str] = (
        "'it also assigns the' statements may appear only at the top of a"
        " global definition block."
    )


# --- Name syntax errors ---


class DefinitionGlobalNameContentRequiresFqun(DefineNameSyntaxError):
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


class GlobalNameWhereLocalNameExpected(DefineTokenError):
    """Wrote something with : and / where a local name was expected."""

    message_format: ClassVar[str] = (
        "This is a global name, but a local name is expected here."
    )


class InvalidGlobalName(DefineTokenError):
    """Wrote something that isn't a global name where only a global name is accepted."""

    message_format: ClassVar[str] = (
        "This is not a valid global name (like 'multiverse:authority:universe:/name')."
    )


class InvalidName(DefineTokenError):
    """Wrote something invalid where either a local or global name is accepted."""

    message_format: ClassVar[str] = (
        "'{token}' is not valid inside of a local or global name."
    )
