"""Error classification logic for the Define parser.

This whole module is an implementation detail of parser.py.
"""

import os

import lark

from define.compiler import parser_exceptions

_CHAR_ERRORS: dict[str, type[parser_exceptions.DefineCharError]] = {
    "\ufeff": parser_exceptions.ByteOrderMarkError,
    "\r": parser_exceptions.CarriageReturnError,
}


def _classify_invalid_char(
    char: str,
) -> type[parser_exceptions.DefineCharError] | None:
    """Classify a character that is always invalid in Define source."""
    char_class = _CHAR_ERRORS.get(char)
    if char_class is not None:
        return char_class
    # C0 control characters (U+0000-U+001F) and DEL (U+007F), excluding newline
    if char != "\n" and (ord(char) < 0x20 or ord(char) == 0x7F):
        return parser_exceptions.ControlCharacterError
    # UTF-16 surrogates (U+D800-U+DFFF), not valid in UTF-8
    if "\ud800" <= char <= "\udfff":
        return parser_exceptions.InvalidEncodingError
    # Any other non-ASCII character
    if ord(char) > 0x7F:
        return parser_exceptions.InvalidCharacterError
    return None


def _is_space_followed_only_by_whitespace(source: str, line: int, column: int) -> bool:
    """Return whether the space is followed only by whitespace on its line."""
    error_line = source.split("\n")[line - 1]
    return not error_line[column:].strip()


def classify_char_error(
    e: lark.exceptions.UnexpectedCharacters,
    source: str,
) -> type[parser_exceptions.DefineCharError] | None:
    """Classify a character rejected by the lexer in a syntax position."""
    char_class = _classify_invalid_char(e.char)
    if char_class is not None:
        return char_class

    if e.char == " " and _is_space_followed_only_by_whitespace(
        source, e.line, e.column
    ):
        return parser_exceptions.TrailingWhitespaceError

    return None


def raise_token_error(
    e: lark.exceptions.UnexpectedToken,
    source: str,
    file_path: str | os.PathLike[str] | None,
):
    """Classify a token error into a specific exception type."""
    ####################################
    ## First Character Classification ##
    ####################################

    # This needs to come first; it's the only error type that reliably escapes control
    # characters.
    if len(e.token) > 0:
        char_error = _classify_invalid_char(e.token[0])
        if char_error:
            raise char_error.from_lark_exception(e, source, e.token[0], file_path)

    if e.token.startswith(" ") and _is_space_followed_only_by_whitespace(
        source, e.line, e.column
    ):
        raise parser_exceptions.TrailingWhitespaceError.from_lark_exception(
            e, source, e.token, file_path
        )

    ###############################
    ## e.accepts Classification ##
    ###############################

    # If we see we need a >, that means we are parsing a name and forgot
    # the closing bracket. We check e.token_history just to make the type
    # checker happy---we always have a token history here.
    if e.accepts == {"MORETHAN"} and e.token_history:
        raise parser_exceptions.MissingCloseAngleBracket(
            e, source, file_path, e.token_history[-1]
        )

    # Same for <, which means the previous token was the start of a definition
    # and we expect a name and didn't get <.
    if e.accepts == {"LESSTHAN"}:
        raise parser_exceptions.MissingOpenAngleBracket(e, source, file_path, e.token)

    # This is just <> or < with nothing after it, while expecting a name.
    if (
        e.accepts == {"NAME_CONTENT"}
        and (e.token == ">" or e.token.type in ("NEWLINE, $END"))
        and e.token_history
        and e.token_history[-1] == "<"
    ):
        raise parser_exceptions.EmptyName(e, source, file_path)

    if e.accepts == {"SPACE_AND_OPEN_BRACE", "DOT"}:
        if e.token == "{":
            raise parser_exceptions.MissingWhitespaceBeforeBrace(e, source, file_path)
        # This happens at least if it's a newline or just a space and a newline.
        raise parser_exceptions.MissingTerminatorOrBrace(e, source, file_path)

    if e.accepts == {"DOT"}:
        raise parser_exceptions.MissingTerminator(e, source, file_path)

    if e.accepts == {"SPACE_AND_OPEN_BRACE"}:
        raise parser_exceptions.MissingOpenBrace(e, source, file_path)

    if e.accepts == {"SPACE"}:
        raise parser_exceptions.MissingWhitespace(e, source, file_path)

    if e.accepts == {"NEWLINE"}:
        # TODO: This EOF one shows up sometimes when we really want MissingCloseBrace.
        if e.token.type == "$END":
            raise parser_exceptions.MissingNewlineAtEof(e, source, file_path)
        if e.token_history:
            match e.token_history[-1].type:
                case "DOT":
                    raise parser_exceptions.MissingNewlineAfterTerminator(
                        e, source, file_path
                    )
                case "SPACE_AND_OPEN_BRACE":
                    if e.token == "}":
                        raise parser_exceptions.EmptyBlock(e, source, file_path)
                    raise parser_exceptions.MissingNewlineAfterOpenBrace(
                        e, source, file_path
                    )
                case "RBRACE":
                    raise parser_exceptions.MissingNewlineAfterCloseBrace(
                        e, source, file_path
                    )
                case _:
                    pass

    if e.accepts == {"NEWLINE", "RBRACE"}:
        # TODO: This may be fragile when we allow this in other places.
        if e.token.type == "DEFINE_THE_POSITION":
            raise parser_exceptions.InvalidPositionDefinitionLocationInAction(
                e, source, file_path
            )
        raise parser_exceptions.MissingCloseBrace(e, source, file_path)

    if e.accepts == {"AND_IT_DOES"}:
        # This catches the case where you put too many spaces before "and it does"
        if "  " in e.token and "and it does" in e.token:
            raise parser_exceptions.ExtraWhitespace(e, source, file_path)
        raise parser_exceptions.MissingActionStatementsBlock(e, source, file_path)

    if e.accepts == {"NAME_TYPE"}:
        raise parser_exceptions.ExpectedNameType(e, source, file_path)

    # This has to be here, because otherwise the "IT_HAPPENS_WHEN" will match
    # when this happens inside an Action Definition Block.
    if "DEFINE_THE_POSITION" in e.accepts and e.token.startswith(
        "define the potential "
    ):
        raise parser_exceptions.GlobalDefinitionInLocalContext(e, source, file_path)

    #######################
    ## Generic Fallbacks ##
    #######################

    # This is a generic fallback because we don't want to mask more specific errors above.
    # (For example, 'position  <foo>' should throw MissingOpenAngleBracket, not this error.)
    # However, it's more specific than the errors below because if you type
    # "define  the potential position" we want to tell you about the whitespace, not other
    # errors.
    #
    # TODO: Ideally, we would actually throw this _before_ all other errors, because it's
    # more helpful in many cases. However, due to the way Lark works, that would require
    # re-lexing and re-parsing the entire file with fixed syntax.
    if "  " in e.token.strip(" "):
        raise parser_exceptions.ExtraWhitespace(e, source, file_path)

    # Because the top-level syntax is so constrained, if we expect a global definition,
    # this error should basically always be the correct one.
    if "DEFINE_THE_POTENTIAL_POSITION" in e.accepts:
        raise parser_exceptions.ExpectedGlobalDefinition(e, source, file_path)

    # A relatively broad fallback for random nonsense inside an Action Definition Block.
    # We use e.accepts here because it's narrower than e.expected.
    if "IT_HAPPENS_WHEN" in e.accepts:
        if e.token == "}":
            # TODO: Needs more context to see the start of the block, not the end of it.
            raise parser_exceptions.MissingActionDefinitionSyntax(e, source, file_path)
        raise parser_exceptions.InvalidActionDefinitionsBlock(e, source, file_path)

    # We are in an Action Statements Block. Need to update this check when
    # other local position definition locations are acceptable in the future.
    # This check must happen after the IT_HAPPENS_WHEN check above.
    if "DEFINE_THE_POSITION" in e.accepts:
        raise parser_exceptions.InvalidActionStatementsBlock(e, source, file_path)

    # We are in a position definition block.
    if "IT_MAY_ONLY_CONTAIN_DIMENSION_POINTS_WHERE" in e.accepts:
        if e.token == "}":
            raise parser_exceptions.MissingPositionDefinitionContent(
                e, source, file_path
            )
        raise parser_exceptions.InvalidPositionDefinitionBlock(e, source, file_path)

    # We are in a position constraint block.
    if "IT_HAS_THE" in e.accepts:
        if e.token == "}":
            raise parser_exceptions.MissingPositionConstraintContent(
                e, source, file_path
            )
        raise parser_exceptions.InvalidPositionConstraintBlock(e, source, file_path)


def make_invalid_encoding_error(
    raw: bytes, e: UnicodeDecodeError, path: os.PathLike[str]
) -> parser_exceptions.InvalidEncodingError:
    """Create an InvalidEncodingError from a UnicodeDecodeError."""
    before = raw[: e.start]
    line = before.count(b"\n") + 1
    last_newline = before.rfind(b"\n")
    column = e.start - last_newline
    context = raw[last_newline + 1 : e.start + 20]
    context_str = context.decode("utf-8", errors="replace")
    bad_byte = f"\\x{raw[e.start]:02x}"
    return parser_exceptions.InvalidEncodingError(
        context_str, line, column, bad_byte, path
    )
