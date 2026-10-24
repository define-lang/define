"""Human-readable parser error messages for the Define language."""

# Add concrete errors to the section for their base class below.
# Keep error classes alphabetical within each section.

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, ClassVar, override

from define.compiler import constants
from define.compiler.errors import exceptions, source_map

if TYPE_CHECKING:
    from define.compiler import ast


class DefineSyntaxError(exceptions.DefineError):
    """Base class for Define syntax errors."""

    message_format: ClassVar[str] = "Syntax error."
    location: ast.SourceLocation

    def __init__(self, location: ast.SourceLocation):
        """Initialize the syntax error with the location of the invalid source."""
        super().__init__(location)
        self.location = location

    def _message_fields(self) -> dict[str, object]:
        """Return fields available for message formatting."""
        return dict(self.__dict__)

    @property
    def message(self) -> str:
        """Render the error message from the format template."""
        return self.message_format.format(**self._message_fields())

    def format(self, sources: source_map.SourceMap) -> str:
        """Format the error with the source code at its location."""
        # A syntax error can be about an invisible character, so it must show.
        location = sources.format_location(
            self.location, escape_invisible_characters=True
        )
        return f"{location}\n{self.message}"


class DefineTokenError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected tokens."""


class DefineCharError(DefineSyntaxError):
    """Base class for Define syntax errors caused by unexpected characters."""

    char: str

    def __init__(self, location: ast.SourceLocation, char: str):
        """Initialize with the unexpected character."""
        super().__init__(location)
        self.char = char

    @property
    def escaped_char(self) -> str:
        """The character in a readable escaped form."""
        return source_map.escape_invisible(self.char)

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


class InvalidLocalNameCharacter(DefineCharError):
    """Wrote something invalid where only a local name is accepted."""

    message_format: ClassVar[str] = "'{escaped_char}' is not allowed in local names."


class InvalidEncodingError(DefineCharError):
    """Raised when a file contains bytes that are not valid UTF-8."""

    message_format: ClassVar[str] = "Invalid UTF-8 byte sequence: ({escaped_char})."


class InvalidLiteralEscape(DefineCharError):
    """An unsupported escape in literal content."""

    message_format: ClassVar[str] = (
        'Invalid escape sequence in this literal. Only \\", \\\\, and \\n are allowed.'
    )


class InvisibleCharacterError(DefineCharError):
    """Raised when a character is invisible and the Invisible Characters rule does not allow it there."""

    message_format: ClassVar[str] = (
        "Invisible character {description} is not allowed here."
    )

    @property
    def description(self) -> str:
        """The character's code point and, when Unicode names it, its name."""
        code_point = f"U+{ord(self.char):04X}"
        name = unicodedata.name(self.char, "")
        return f"{code_point} {name}" if name else code_point

    @override
    def _message_fields(self) -> dict[str, object]:
        fields = super()._message_fields()
        fields["description"] = self.description
        return fields


# --- Token error subclasses ---

# The token error subclasses don't use the suffix "Error." Instead, they are expressed
# as the name of the problem, which is much more intuitive to type and read.
#
# Keep these in alphabetical order.


class ChainedNameInPositionPresenceStatement(DefineTokenError):
    """Wrote a chained name in a position presence statement."""

    message_format: ClassVar[str] = (
        "A position presence statement only accepts a single local name, like:\n"
        "    the position<foo> has a particle.\n"
        "Chained names (with '::') are not allowed here."
    )


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


class ExpectedQualityAssignmentNameType(DefineTokenError):
    """Expected a quality type in a Quality Assignment Statement."""

    message_format: ClassVar[str] = (
        "Expected 'position', 'action', 'value', or 'encoding'."
    )


class ExpectedGlobalDefinition(DefineTokenError):
    """Thrown when the parser expected to see a global definition and didn't see one."""

    message_format: ClassVar[str] = (
        "Expected a global definition, one of:\n"
        + "    - define the potential position\n"
        + "    - define the potential action\n"
        + "\n"
        + "Or less commonly:\n"
        + "    - define the potential value\n"
        + "    - define the potential literal\n"
        + "    - define the encoding\n"
        + "    - define the operation\n"
        + "    - define the encoding_operation"
    )


class ExpectedOperation(DefineTokenError):
    """Expected an operation name in an Operation Execution Statement."""

    message_format: ClassVar[str] = "Expected 'operation'."


class ExpectedEncodingOperation(DefineTokenError):
    """Expected an Encoding Operation name in an Encoding Operation Execution Statement."""

    message_format: ClassVar[str] = "Expected 'encoding_operation'."


class ExpectedPositionOrAction(DefineTokenError):
    """Expected a position or action reference."""

    message_format: ClassVar[str] = "Expected 'position' or 'action'."


class ExpectedPositionOrActionOrLiteral(DefineTokenError):
    """Expected a position reference or a literal."""

    message_format: ClassVar[str] = "Expected 'position', 'action', or 'literal'."


class ExpectedValueSource(DefineTokenError):
    """Expected what an Operation Argument Statement is looking at."""

    message_format: ClassVar[str] = (
        "Expected 'position', 'action', 'view', or 'literal'."
    )


class ExpectedView(DefineTokenError):
    """Expected a view name in an Operation Argument Statement."""

    message_format: ClassVar[str] = "Expected 'view'."


class ExtraWhitespace(DefineTokenError):
    """When you write two spaces where you should have written one."""

    message_format: ClassVar[str] = (
        "Line looks like it contains too many spaces between words."
        + " All words in Define require exactly one space between them."
    )


class GlobalNameWhereLocalNameExpected(DefineTokenError):
    """Wrote something with : and / where a local name was expected."""

    message_format: ClassVar[str] = (
        "This is a global name, but a local name is expected here."
    )


class GlobalPositionDefinitionInLocalContext(DefineTokenError):
    """Wrote 'define the potential position' where only 'define the position' is accepted."""

    message_format: ClassVar[str] = (
        "Global position definition not allowed here."
        " Write 'define the position' instead of 'define the potential position'."
    )


class InvalidActionDefinitionsBlock(DefineTokenError):
    """Wrote something totally invalid in an Action Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a potential action definition."


class InvalidActionStatementsBlock(DefineTokenError):
    """Nonsense in an Action Statements Block."""

    message_format: ClassVar[str] = "Not a valid action statement or local definition."


class InvalidGlobalName(DefineTokenError):
    """Wrote something that isn't a global name where only a global name is accepted."""

    message_format: ClassVar[str] = (
        "This is not a valid global name (like 'multiverse:authority:universe:/name')."
    )


class InvalidHasAParticleSyntax(DefineTokenError):
    """Expected 'has a particle' after a local name in a trigger condition."""

    message_format: ClassVar[str] = (
        "The syntax for a particle presence check looks like:\n"
        "    the position<foo> has a particle.\n"
        "Expected 'has a particle' here."
    )


class InvalidMoveStatementSyntax(DefineTokenError):
    """Expected 'to' or '::' after a position reference in a move statement."""

    message_format: ClassVar[str] = (
        "The syntax for a move statement looks like:\n"
        "    move the particle in position<foo> to position<bar>.\n"
        "Expected a 'to' or a longer chained name (a '::' followed by another name) here."
    )


class InvalidName(DefineTokenError):
    """Wrote something invalid where either a local or global name is accepted."""

    token: str
    message_format: ClassVar[str] = (
        "'{token}' is not valid inside of a local or global name."
    )

    def __init__(self, location: ast.SourceLocation, token: str):
        """Initialize with the text that is not valid in a name."""
        super().__init__(location)
        self.token = token


class InvalidOperationArgumentsBlock(DefineTokenError):
    """Wrote something other than an Operation Argument Statement in an Operation Arguments Block."""

    message_format: ClassVar[str] = (
        "Operation arguments blocks must contain one or more statements like:\n"
        "    with view<name> looking at position<foo>."
    )


class InvalidOperationArgumentSyntax(DefineTokenError):
    """Expected ' looking at ' after the view name in an Operation Argument Statement."""

    message_format: ClassVar[str] = (
        "The syntax for an operation argument looks like:\n"
        "    with view<name> looking at position<foo>.\n"
        "The position may also be a literal."
    )


class InvalidOperationDefinitionBlock(DefineTokenError):
    """Wrote something invalid in an Operation Definition Block."""

    message_format: ClassVar[str] = (
        "An operation definition may contain 'define the view' definitions"
        " and must end with an 'it does' block."
    )


class InvalidOperationStatementsBlock(DefineTokenError):
    """Wrote something other than an operation statement in an Operation Statements Block."""

    message_format: ClassVar[str] = (
        "Operation statements blocks must contain one or more"
        " 'execute the operation<...>' or 'execute the encoding operation.' statements."
    )


class InvalidEncodingOperationStatementsBlock(DefineTokenError):
    """Wrote something other than an Encoding Operation statement in an Encoding Operation Statements Block."""

    message_format: ClassVar[str] = (
        "Encoding operation statements blocks must contain one or more"
        " 'execute the encoding_operation<...>' or"
        " 'execute the computer operation.' statements."
    )


class InvalidQualityAssignmentBlock(DefineTokenError):
    """Write something nonsensical in a Quality Assignment Block."""

    message_format: ClassVar[str] = "Invalid syntax in a quality assignment block."


class InvalidPositionDefinitionBlock(DefineTokenError):
    """Write something nonsensical in a Position Definition Block."""

    message_format: ClassVar[str] = "Invalid syntax in a position definition."


class InvalidPositionDefinitionLocationInAction(DefineTokenError):
    """Wrote 'define the position' after the action statements block."""

    message_format: ClassVar[str] = (
        "'define the position' statements in an action must go above the 'it happens when' block."
    )


class InvalidPotentialLiteralDefinitionBlock(DefineTokenError):
    """Expected the encoding Quality Assignment Statement of a potential literal."""

    message_format: ClassVar[str] = (
        "A potential literal definition requires exactly one 'it has the encoding<...>.' statement."
    )


class InvalidTriggerConditionsBlock(DefineTokenError):
    """Nonsense in a Trigger Conditions Block."""

    message_format: ClassVar[str] = "Not a valid trigger condition statement."


class InvalidValueSettingStatementSyntax(DefineTokenError):
    """Invalid target or source syntax in a Value Setting Statement."""

    message_format: ClassVar[str] = (
        "The syntax for a value setting statement looks like:\n"
        "    set the value of position<target> to position<source>.\n"
        "The source may also be a literal."
    )


class InvalidViewDirectionStatementOrder(DefineTokenError):
    """Repeated a View Direction Statement or put them in the wrong order."""

    message_format: ClassVar[str] = (
        "A view definition must start with 'it is read.', 'it is written.', or both,"
        " in that order, with each at most once."
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

    def __init__(self, location: ast.SourceLocation, name: str):
        """Initialize with the parsed name token that missed '>'."""
        super().__init__(location)
        self.name = name


class MissingCloseBrace(DefineTokenError):
    """Forgot to write } at the end of a block."""

    message_format: ClassVar[str] = "Missing a closing '}}' somewhere in this block."


class MissingLiteralContentEnd(DefineTokenError):
    """Literal content without a '"' after it on its line."""

    message_format: ClassVar[str] = (
        "This literal's content has no closing '\"' before the end of the line."
    )


class MissingLiteralContentStart(DefineTokenError):
    """A literal without a '"' right after its typed name."""

    message_format: ClassVar[str] = (
        "A literal's content must start with '\"' right after the '>' of its typed name."
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


class MissingEncodingOperationStatementsContent(DefineTokenError):
    """Left out the statements of an Encoding Operation Statements Block."""

    message_format: ClassVar[str] = (
        "Encoding operation statements blocks must contain at least one"
        " 'execute the encoding_operation<...>' or"
        " 'execute the computer operation.' statement."
    )


class MissingOpenAngleBracket(DefineTokenError):
    """A missing < on a name (could be just a raw "define the position", too)."""

    message_format: ClassVar[str] = "Missing '<' at the start of a name."


class MissingOpenBrace(DefineTokenError):
    """Forgot the { in a situation where only that is valid."""

    message_format: ClassVar[str] = (
        "This line must end with a single space followed by a '{{'."
    )


class MissingOperationArgumentsContent(DefineTokenError):
    """Left out the Operation Argument Statements of an Operation Arguments Block."""

    message_format: ClassVar[str] = (
        "Operation arguments blocks must contain at least one"
        " 'with view<...> looking at ...' statement."
    )


class MissingOperationStatementsBlock(DefineTokenError):
    """Left out the 'it does' block of an Operation Definition Block."""

    message_format: ClassVar[str] = (
        "Missing 'it does' block in this operation definition."
    )


class MissingOperationStatementsContent(DefineTokenError):
    """Left out the statements of an Operation Statements Block."""

    message_format: ClassVar[str] = (
        "Operation statements blocks must contain at least one"
        " 'execute the operation<...>' or 'execute the encoding operation.' statement."
    )


class MissingPositionReference(DefineTokenError):
    """A statement ends where a position reference must follow."""

    message_format: ClassVar[str] = (
        "Expected a position reference here, such as 'position<foo>'."
    )


class MissingQualityAssignmentBlockContent(DefineTokenError):
    """Left out syntax from a Quality Assignment Block."""

    message_format: ClassVar[str] = (
        "Quality assignment blocks must contain at least one 'it has the' statement."
    )


class MissingPositionDefinitionContent(DefineTokenError):
    """Left out mandatory content from a position definition block."""

    message_format: ClassVar[str] = (
        "Position definition blocks must contain an"
        " 'it may only contain particles where' block."
        " If you want an empty position definition, end it with a period (.) instead of a block ({{}})."
    )


class MissingSpaceBeforeComment(DefineTokenError):
    """A comment directly after a statement terminator, without a space."""

    message_format: ClassVar[str] = (
        "A comment after a statement terminator must be separated from the '.' by"
        + " a space."
    )


class MissingSpaceBeforeCommentAfterBrace(DefineTokenError):
    """A comment directly after a { or }, without a space."""

    message_format: ClassVar[str] = (
        "'{{' or '}}' must have a space after it, before a comment."
    )


class MissingTerminator(DefineTokenError):
    """Forgot ."""

    message_format: ClassVar[str] = "This statement must end with a '.'."


class MissingTerminatorOrBrace(DefineTokenError):
    """Forgot . or {."""

    message_format: ClassVar[str] = (
        "This statement must end with a '.' or a single space followed by '{{'"
    )


class MissingTriggerConditionContent(DefineTokenError):
    """Left out content from a trigger conditions block."""

    message_format: ClassVar[str] = (
        "Trigger conditions blocks must contain at least one 'the ... has a particle.' statement."
    )


class MissingValueSource(DefineTokenError):
    """A value setting statement ends where its source must follow."""

    message_format: ClassVar[str] = (
        "Expected a position reference or literal here, such as 'position<foo>'."
    )


class MissingViewQualityAssignmentBlock(DefineTokenError):
    """Left out the View Quality Assignment Block after a view's View Direction Statements."""

    message_format: ClassVar[str] = (
        "A view definition must contain an 'it may only contain particles where'"
        " block after its 'it is read.' and 'it is written.' statements."
    )


class MissingViewDirectionStatement(DefineTokenError):
    """Left out the View Direction Statements at the start of a view definition."""

    message_format: ClassVar[str] = (
        "A view definition must start with 'it is read.', 'it is written.', or both."
    )


class MissingWhitespace(DefineTokenError):
    """Forgot required whitespace."""

    message_format: ClassVar[str] = "Missing a space."


class MissingWhitespaceBeforeBrace(DefineTokenError):
    """Forgot to put a space before {."""

    message_format: ClassVar[str] = "Missing a space before '{{'"


class SpaceBeforeOpenAngleBracket(DefineTokenError):
    """Put spaces between a name type and the < of its name."""

    message_format: ClassVar[str] = (
        "A name type and the '<' that starts the name cannot have spaces between them."
    )


class QualityImplicationInWrongOrder(DefineTokenError):
    """Wrote an 'it also assigns the' statement after another statement in an action definition block."""

    message_format: ClassVar[str] = (
        "'it also assigns the' statements must come before every other"
        " statement in an action definition block."
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
        f"'<authority:universe:/path>' or '<{constants.STANDARD_UNIVERSE}:/path>'."
    )
