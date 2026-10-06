"""Error classification logic for the Define parser.

This whole module is an implementation detail of parser.py.
"""

from __future__ import annotations

import typing

import lark_cython

from define.compiler import ast
from define.compiler.errors import parser_exceptions
from define.compiler.parsing.lark import lark_standalone

if typing.TYPE_CHECKING:
    import pathlib

_CHAR_ERRORS: dict[str, type[parser_exceptions.DefineCharError]] = {
    "\ufeff": parser_exceptions.ByteOrderMarkError,
    "\r": parser_exceptions.CarriageReturnError,
    # Direction marks are allowed only in comments, so the lexer rejects them
    # everywhere else.
    "\u061c": parser_exceptions.InvisibleCharacterError,
    "\u200e": parser_exceptions.InvisibleCharacterError,
    "\u200f": parser_exceptions.InvisibleCharacterError,
}


def classify_invalid_char(
    char: str,
) -> type[parser_exceptions.DefineCharError] | None:
    """Classify a character that is always invalid in Define source."""
    char_class = _CHAR_ERRORS.get(char)
    if char_class is not None:
        return char_class
    # C0 control characters (U+0000-U+001F), DEL (U+007F), and C1 control
    # characters (U+0080-U+009F), excluding newline
    if char != "\n" and (ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F):
        return parser_exceptions.ControlCharacterError
    # UTF-16 surrogates (U+D800-U+DFFF), not valid in UTF-8
    if "\ud800" <= char <= "\udfff":
        return parser_exceptions.InvalidEncodingError
    # Any other non-ASCII character
    if ord(char) > 0x7F:
        return parser_exceptions.InvalidCharacterError
    return None


def _stripped_context(source: str, line: int, column: int) -> str:
    error_line = source.split("\n")[line - 1]
    return error_line[column:].strip()


def _is_in_view_definition(e: lark_standalone.UnexpectedToken) -> bool:
    interactive_parser = typing.cast(
        "lark_standalone.InteractiveParser", e.interactive_parser
    )
    for item in interactive_parser.parser_state.value_stack:
        if isinstance(item, lark_cython.Token) and item.type == "DEFINE_THE_VIEW":
            return True
    return False


def _end_of_file_error_with_final_newline(
    e: lark_standalone.UnexpectedToken,
    source: str,
    file_path: pathlib.PurePosixPath | None,
) -> lark_standalone.UnexpectedToken:
    """Return the end-of-file error as it would be if the file ended with a newline.

    Raises MissingNewlineAtEof if the final newline is the only thing missing.
    """
    # Classify as though the file ended with its required newline, so that a
    # missing final newline does not hide a more important error.
    if source.endswith("\n") or "NEWLINE" not in e.accepts:
        return e
    interactive_parser = typing.cast(
        "lark_standalone.InteractiveParser", e.interactive_parser
    )
    interactive_parser.feed_token(
        lark_cython.Token.new_borrow_pos("NEWLINE", "\n", e.token)
    )
    accepts = interactive_parser.accepts()
    if "$END" in accepts:
        raise parser_exceptions.MissingNewlineAtEof(e, file_path)
    return lark_standalone.UnexpectedToken(
        lark_cython.Token.new_borrow_pos("$END", "", e.token),
        accepts,
        interactive_parser=interactive_parser,
    )


def _ends_block(token: lark_cython.Token) -> bool:
    return token.type in {"CLOSE_BRACE", "$END"}


_STATEMENT_END_TOKEN_TYPES = frozenset({"DOT", "NEWLINE", "$END"})


def _error_with_missing_space(
    e: lark_standalone.UnexpectedToken,
    file_path: pathlib.PurePosixPath | None,
) -> lark_standalone.UnexpectedToken:
    """Return the error as it would be if the expected space were present.

    Raises MissingWhitespace if the space is the only thing missing.
    """
    interactive_parser = typing.cast(
        "lark_standalone.InteractiveParser", e.interactive_parser
    )
    interactive_parser.feed_token(
        lark_cython.Token.new_borrow_pos("SPACE", " ", e.token)
    )
    accepts = interactive_parser.accepts()
    if e.token.type in accepts:
        raise parser_exceptions.MissingWhitespace(e, file_path)
    return lark_standalone.UnexpectedToken(
        e.token,
        accepts,
        interactive_parser=interactive_parser,
        token_history=e.token_history,
    )


def raise_character_error(
    e: lark_standalone.UnexpectedCharacters,
    file_path: pathlib.PurePosixPath | None,
):
    """Classify an error for a character that no terminal matches."""
    char_error = classify_invalid_char(e.char)
    if char_error:
        raise char_error.from_lark_exception(e, e.char, file_path)


def raise_token_error(
    e: lark_standalone.UnexpectedToken,
    source: str,
    file_path: pathlib.PurePosixPath | None,
):
    """Classify a token error into a specific exception type."""
    ##################################
    # First Character Classification #
    ##################################

    # This needs to come first; it's the only error type that reliably escapes control
    # characters.
    if len(e.token.value) > 0:
        char_error = classify_invalid_char(e.token.value[0])
        if char_error:
            raise char_error.from_lark_exception(e, e.token.value[0], file_path)

    # If there's a space followed only by other spaces.
    if e.token.value.startswith(" ") and not _stripped_context(
        source, e.line, e.column
    ):
        raise parser_exceptions.TrailingWhitespaceError.from_lark_exception(
            e, e.token.value, file_path
        )

    if (
        e.token.type == "SPACE"
        and e.token_history
        and e.token_history[-1] is not None
        and e.token_history[-1].type == "SPACE"
    ):
        raise parser_exceptions.ExtraWhitespace(e, file_path)

    ##############################
    # End of File Classification #
    ##############################

    if e.token.type == "$END":
        # We classify an EOF like a '}' at the same point, so a
        # block that still needs content reports the missing content.
        e = _end_of_file_error_with_final_newline(e, source, file_path)
        if "CLOSE_BRACE" in e.accepts:
            raise parser_exceptions.MissingCloseBrace(e, file_path)

    if "SPACE" in e.accepts:
        e = _error_with_missing_space(e, file_path)

    ############################
    # e.accepts Classification #
    ############################

    if e.accepts in ({"DBLQUOTE"}, {"LITERAL_CONTENT", "DBLQUOTE"}):
        raise parser_exceptions.InvalidLiteralSyntax(e, file_path)

    # < means the previous token was the start of a definition
    # and we expect a name and didn't get <.
    if e.accepts == {"LESSTHAN"}:
        raise parser_exceptions.MissingOpenAngleBracket(e, file_path, e.token.value)

    # This is just <> or < with nothing after it, while expecting a name.
    if ("GLOBAL_NAME_CONTENT" in e.accepts or "LOCAL_NAME_CONTENT" in e.accepts) and (
        e.token.value == ">" or e.token.type in {"NEWLINE", "$END"}
    ):
        raise parser_exceptions.EmptyName(e, file_path)

    if e.accepts == {"LOCAL_NAME_CONTENT"}:
        raise parser_exceptions.InvalidLocalNameCharacter.from_lark_exception(
            e, e.token.value[0], file_path
        )

    if e.accepts == {"GLOBAL_NAME_CONTENT"}:
        raise parser_exceptions.InvalidGlobalName(e, file_path)

    if e.accepts == {"LOCAL_NAME_CONTENT", "GLOBAL_NAME_CONTENT"}:
        raise parser_exceptions.InvalidName(e, file_path)

    if e.accepts == {"MORETHAN"}:
        # Literal content makes ':' lexable even when it occurs in a local name.
        if e.token.type == "LITERAL_CONTENT":
            raise parser_exceptions.InvalidLocalNameCharacter.from_lark_exception(
                e, e.token.value[0], file_path
            )
        # In a local name like "my/pos", "my" has already been consumed and
        # "/pos" matches global name content.
        if e.token.type == "GLOBAL_NAME_CONTENT":
            raise parser_exceptions.GlobalNameWhereLocalNameExpected(e, file_path)
        if e.token_history:
            previous_token = typing.cast("lark_cython.Token", e.token_history[-1])
            raise parser_exceptions.MissingCloseAngleBracket(
                e, file_path, previous_token.value
            )
        # Due to some quirks of Lark, $END never has token_history.
        if e.token.type == "$END":
            raise parser_exceptions.MissingCloseAngleBracket(
                e, file_path, source[e.token.start_pos : e.token.end_pos]
            )

    if e.accepts == {"SPACE_AND_OPEN_BRACE", "DOT"}:
        if e.token.value == "{":
            raise parser_exceptions.MissingWhitespaceBeforeBrace(e, file_path)
        # This happens at least if it's a newline or just a space and a newline.
        raise parser_exceptions.MissingTerminatorOrBrace(e, file_path)

    if e.accepts == {"HAS_A_PARTICLE"}:
        raise parser_exceptions.InvalidHasAParticleSyntax(e, file_path)

    if e.accepts == {"DOT"}:
        raise parser_exceptions.MissingTerminator(e, file_path)

    if e.accepts == {"SPACE_AND_OPEN_BRACE"}:
        if e.token.value == " ":
            raise parser_exceptions.ExtraWhitespace(e, file_path)
        raise parser_exceptions.MissingOpenBrace(e, file_path)

    if e.accepts == {"NEWLINE"} and e.token_history:
        previous_token = typing.cast("lark_cython.Token", e.token_history[-1])
        match previous_token.type:
            case "DOT":
                raise parser_exceptions.MissingNewlineAfterTerminator(e, file_path)
            case "SPACE_AND_OPEN_BRACE":
                if e.token.value == "}":
                    raise parser_exceptions.EmptyBlock(e, file_path)
                raise parser_exceptions.MissingNewlineAfterOpenBrace(e, file_path)
            case "CLOSE_BRACE":
                raise parser_exceptions.MissingNewlineAfterCloseBrace(e, file_path)
            case _:
                pass

    if e.accepts == {"NEWLINE", "CLOSE_BRACE"}:
        # TODO: This may be fragile when we allow this in other places.
        if e.token.type == "DEFINE_THE_POSITION":
            raise parser_exceptions.InvalidPositionDefinitionLocationInAction(
                e, file_path
            )
        if e.token.type == "IT_ALSO_ASSIGNS_THE":
            raise parser_exceptions.QualityImplicationInWrongLocation(e, file_path)
        if e.token.type in {
            "IT_IS_READ",
            "IT_IS_WRITTEN",
        } and _is_in_view_definition(e):
            raise parser_exceptions.InvalidViewDirectionStatementOrder(e, file_path)
        raise parser_exceptions.MissingCloseBrace(e, file_path)

    if e.accepts == {"AND_IT_DOES"}:
        # This catches the case where you put too many spaces before "and it does"
        if e.token.value == " ":
            raise parser_exceptions.ExtraWhitespace(e, file_path)
        raise parser_exceptions.MissingActionStatementsBlock(e, file_path)

    if e.accepts == {"POSITION_OR_ACTION"}:
        if e.token.type in _STATEMENT_END_TOKEN_TYPES:
            raise parser_exceptions.MissingPositionReference(e, file_path)
        raise parser_exceptions.ExpectedPositionOrAction(e, file_path)

    if e.accepts == {"POSITION_OR_ACTION", "LITERAL"}:
        if e.token.type in _STATEMENT_END_TOKEN_TYPES:
            raise parser_exceptions.MissingValueSource(e, file_path)
        raise parser_exceptions.ExpectedPositionOrActionOrLiteral(e, file_path)

    if e.accepts == {"POSITION_OR_ACTION", "VIEW", "LITERAL"}:
        raise parser_exceptions.ExpectedValueSource(e, file_path)

    if e.accepts == {"POSITION_OR_ACTION", "VALUE", "ENCODING"}:
        raise parser_exceptions.ExpectedConstraintNameType(e, file_path)

    if e.accepts == {"OPERATION"}:
        raise parser_exceptions.ExpectedOperation(e, file_path)

    if e.accepts == {"ENCODING_OPERATION"}:
        raise parser_exceptions.ExpectedEncodingOperation(e, file_path)

    if e.accepts == {"VIEW"}:
        raise parser_exceptions.ExpectedView(e, file_path)

    if e.accepts == {"LOOKING_AT"}:
        raise parser_exceptions.InvalidOperationArgumentSyntax(e, file_path)

    # These blocks also accept '}' once they contain at least one statement or
    # argument.
    accepts_in_block = e.accepts - {"CLOSE_BRACE"}

    if accepts_in_block == {"WITH", "NEWLINE"}:
        raise parser_exceptions.InvalidOperationArgumentsBlock(e, file_path)

    if e.accepts == {"DEFINE_THE_VIEW", "IT_DOES", "NEWLINE"}:
        raise parser_exceptions.InvalidOperationDefinitionBlock(e, file_path)

    if accepts_in_block == {"EXECUTE_THE", "EXECUTE_THE_ENCODING_OPERATION", "NEWLINE"}:
        raise parser_exceptions.InvalidOperationStatementsBlock(e, file_path)

    if accepts_in_block == {"EXECUTE_THE", "EXECUTE_THE_COMPUTER_OPERATION", "NEWLINE"}:
        raise parser_exceptions.InvalidEncodingOperationStatementsBlock(e, file_path)

    if e.accepts == {"ENCODING"}:
        raise parser_exceptions.InvalidPotentialLiteralDefinitionBlock(e, file_path)

    # TODO: After changing the priority of the *_NAME_CONTENT terminals, I think
    # we could do better here.
    if e.accepts in ({"CHAIN_SEPARATOR", "TO"}, {"TO"}):
        # The statement keyword remains on the stack until the statement reduces,
        # even when token_history is absent or the position has not reduced at EOF.
        interactive_parser = typing.cast(
            "lark_standalone.InteractiveParser", e.interactive_parser
        )
        for item in reversed(interactive_parser.parser_state.value_stack):
            if isinstance(item, lark_cython.Token):
                if item.type == "SET_THE_VALUE_OF":
                    raise parser_exceptions.InvalidValueSettingStatementSyntax(
                        e, file_path
                    )
                if item.type == "MOVE_THE_PARTICLE_IN":
                    raise parser_exceptions.InvalidMoveStatementSyntax(e, file_path)

    if e.accepts == {"CHAIN_SEPARATOR", "DOT"}:
        raise parser_exceptions.ExpectedChainSeparatorOrTerminator(e, file_path)

    if e.accepts == {"NEWLINE", "THE", "CONSTRUCTOR_STATEMENT", "DESTRUCTOR_STATEMENT"}:
        if _ends_block(e.token):
            raise parser_exceptions.MissingTriggerConditionContent(e, file_path)
        if e.token.type == "IT_ALSO_ASSIGNS_THE":
            raise parser_exceptions.QualityImplicationInWrongLocation(e, file_path)
        raise parser_exceptions.InvalidTriggerConditionsBlock(e, file_path)

    # This has to be here, because otherwise the "IT_HAPPENS_WHEN" will match
    # when this happens inside an Action Definition Block.
    if (
        "DEFINE_THE_POSITION" in e.accepts
        and e.token.type == "DEFINE_THE_POTENTIAL_POSITION"
    ):
        raise parser_exceptions.GlobalPositionDefinitionInLocalContext(e, file_path)

    #####################
    # Generic Fallbacks #
    #####################

    # This is a generic fallback because we don't want to mask more specific errors above.
    # (For example, 'position  <foo>' should throw MissingOpenAngleBracket, not this error.)
    # However, it's more specific than the errors below because if you type
    # "define  the potential position" we want to tell you about the whitespace, not other
    # errors.
    #
    # TODO: Ideally, we would actually throw this _before_ all other errors, because it's
    # more helpful in many cases. However, due to the way Lark works, that would require
    # re-lexing and re-parsing the entire file with fixed syntax.
    if "  " in _stripped_context(source, e.line, e.column):
        raise parser_exceptions.ExtraWhitespace(e, file_path)

    # Because the top-level syntax is so constrained, if we expect a global definition,
    # this error should basically always be the correct one.
    if "DEFINE_THE_POTENTIAL_POSITION" in e.accepts:
        raise parser_exceptions.ExpectedGlobalDefinition(e, file_path)

    # An implication keyword the parser rejects must be in the wrong place inside a
    # definition. Placed after the global-definition fallback so a stray implication at
    # the top level still surfaces as ExpectedGlobalDefinition (the user likely just
    # forgot to start a definition).
    if e.token.type == "IT_ALSO_ASSIGNS_THE":
        raise parser_exceptions.QualityImplicationInWrongLocation(e, file_path)

    # A relatively broad fallback for random nonsense inside an Action Definition Block.
    if "IT_HAPPENS_WHEN" in e.accepts:
        if _ends_block(e.token):
            # TODO: Needs more context to see the start of the block, not the end of it.
            raise parser_exceptions.MissingActionDefinitionSyntax(e, file_path)
        raise parser_exceptions.InvalidActionDefinitionsBlock(e, file_path)

    # We are in an Action Statements Block. Need to update this check when
    # other local position definition locations are acceptable in the future.
    # This check must happen after the IT_HAPPENS_WHEN check above.
    if "DEFINE_THE_POSITION" in e.accepts:
        raise parser_exceptions.InvalidActionStatementsBlock(e, file_path)

    # We are in a potential position definition block (global, not local).
    # This must come before the local position definition block check below,
    # because IT_ALSO_ASSIGNS_THE (quality implications are only allowed in a
    # potential position block) distinguishes the potential block from local.
    if "IT_ALSO_ASSIGNS_THE" in e.accepts:
        if _ends_block(e.token):
            raise parser_exceptions.MissingPotentialPositionDefinitionContent(
                e, file_path
            )
        raise parser_exceptions.InvalidPotentialPositionDefinitionBlock(e, file_path)

    # We are at the start of a view definition block.
    if "IT_IS_READ" in e.accepts:
        raise parser_exceptions.MissingViewDirectionStatement(e, file_path)

    # We are after the View Direction Statements of a view definition block.
    if "IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE" in e.accepts and _is_in_view_definition(e):
        if e.token.type in {"IT_IS_READ", "IT_IS_WRITTEN"}:
            raise parser_exceptions.InvalidViewDirectionStatementOrder(e, file_path)
        raise parser_exceptions.InvalidViewDefinitionBlock(e, file_path)

    # We are in a position definition block.
    if "IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE" in e.accepts:
        if _ends_block(e.token):
            raise parser_exceptions.MissingPositionDefinitionContent(e, file_path)
        raise parser_exceptions.InvalidPositionDefinitionBlock(e, file_path)

    # We are in a position constraint block.
    if "IT_HAS_THE" in e.accepts:
        interactive_parser = typing.cast(
            "lark_standalone.InteractiveParser", e.interactive_parser
        )
        for item in interactive_parser.parser_state.value_stack:
            if (
                isinstance(item, lark_cython.Token)
                and item.type == "DEFINE_THE_POTENTIAL_LITERAL"
            ):
                raise parser_exceptions.InvalidPotentialLiteralDefinitionBlock(
                    e, file_path
                )
        if _ends_block(e.token):
            raise parser_exceptions.MissingPositionConstraintContent(e, file_path)
        raise parser_exceptions.InvalidPositionConstraintBlock(e, file_path)


def make_invalid_encoding_error(
    raw: bytes, e: UnicodeDecodeError, path: pathlib.PurePosixPath
) -> parser_exceptions.InvalidEncodingError:
    """Create an InvalidEncodingError from a UnicodeDecodeError."""
    before = raw[: e.start]
    line = before.count(b"\n") + 1
    line_start = before.rfind(b"\n") + 1
    # Everything before the first invalid byte is valid UTF-8.
    column = len(raw[line_start : e.start].decode("utf-8")) + 1
    bad_byte = f"\\x{raw[e.start]:02x}"
    return parser_exceptions.InvalidEncodingError(
        ast.SourceLocation(
            line=line,
            column=column,
            end_line=line,
            end_column=column + 1,
            file_path=path,
        ),
        bad_byte,
    )
