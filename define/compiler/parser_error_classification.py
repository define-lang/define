"""Error classification logic for the Define parser."""

import os
from collections.abc import Callable

from lark import Token, Tree, exceptions

from define.compiler import parser_exceptions

_TOKEN_ERROR_EXAMPLES: dict[type[parser_exceptions.DefineTokenError], list[str]] = {
    parser_exceptions.MissingBlockCloseError: [
        "define the potential position<standard:/path> {\n",
        "define the potential position<standard:/a/path> {\n",
        "define the potential position<example.com:my_lib:/path> {\n",
        "define the potential position<example.com:my_lib:/a/path> {\n",
        "define the potential position<mymv:example.com:my_lib:/path> {\n",
        "define the potential position<mymv:example.com:my_lib:/a/path> {\n",
        "define the potential action<standard:/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
        "define the potential action<standard:/a/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
        "define the potential action<example.com:my_lib:/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
        "define the potential action<example.com:my_lib:/a/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
        "define the potential action<mymv:example.com:my_lib:/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
        "define the potential action<mymv:example.com:my_lib:/a/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n",
    ],
    parser_exceptions.EmptyBlockTerminatorError: [
        "define the potential position<standard:/path> {\n}\n",
        "define the potential position<standard:/a/path> {\n}\n",
        "define the potential position<standard:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "}\n"
        + "}\n",
        "define the potential position<standard:/a/path> {\n"
        + "it may only contain dimension points where {\n"
        + "}\n"
        + "}\n",
        "define the potential action<standard:/path> {\n}\n",
        "define the potential action<standard:/a/path> {\n}\n",
        "define the potential action<example.com:my_lib:/path> {\n}\n",
        "define the potential action<example.com:my_lib:/a/path> {\n}\n",
        "define the potential action<mymv:example.com:my_lib:/path> {\n}\n",
        "define the potential action<mymv:example.com:my_lib:/a/path> {\n}\n",
        "define the potential action<standard:/path> {\n"
        + "define the position<x>.\n"
        + "}\n",
        "define the potential action<standard:/a/path> {\n"
        + "define the position<x>.\n"
        + "}\n",
    ],
    parser_exceptions.MissingActionStatementsBlockError: [
        "define the potential action<standard:/path> {\n"
        + "it happens when {\n"
        + "}\n",
        "define the potential action<standard:/a/path> {\n"
        + "it happens when {\n"
        + "}\n",
    ],
    parser_exceptions.MissingNewlineAfterBlockCloseError: [
        "define the potential action<standard:/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}}\n",
        "define the potential action<standard:/a/path> {\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}}\n",
    ],
    parser_exceptions.MissingNewlineAfterBlockOpenError: [
        "define the potential position<standard:/path> {}\n",
        "define the potential position<standard:/a/path> {}\n",
        "define the potential position<example.com:my_lib:/path> {}\n",
        "define the potential position<example.com:my_lib:/a/path> {}\n",
        "define the potential position<mymv:example.com:my_lib:/path> {}\n",
        "define the potential position<mymv:example.com:my_lib:/a/path> {}\n",
        "define the potential action<standard:/path> {}\n",
        "define the potential action<standard:/a/path> {}\n",
        "define the potential action<example.com:my_lib:/path> {}\n",
        "define the potential action<example.com:my_lib:/a/path> {}\n",
        "define the potential action<mymv:example.com:my_lib:/path> {}\n",
        "define the potential action<mymv:example.com:my_lib:/a/path> {}\n",
    ],
    parser_exceptions.MissingTerminatorError: [
        "define the potential position<standard:/path>\n",
    ],
    parser_exceptions.MissingNewlineError: [
        "define the potential position<standard:/path>.",
    ],
    parser_exceptions.MissingOpenAngleBracketError: [
        "define the potential positionstandard:/path>.\n",
    ],
    parser_exceptions.MissingCloseAngleBracketError: [
        "define the potential position<standard:/path.\n",
        "define the potential position<mymv:example.com:my_lib:/path.\n",
        "define the potential position<mymv:example.com:my_lib:/a/path.\n",
    ],
    parser_exceptions.EmptyNameError: [
        "define the potential position<>.\n",
        "define the potential action<standard:/act> {\n"
        + "define the position<>.\n"
        + "it happens when {\n"
        + "} and it does {\n"
        + "}\n"
        + "}\n",
    ],
    parser_exceptions.EmptyFileError: [
        "",
        "\n\n\n",
        "# a comment",
    ],
    parser_exceptions.IncompleteStatementError: [
        "define the potential\n",
        "define the potential.\n",
        "define the\n",
        "define the.\n",
    ],
    parser_exceptions.UnexpectedWhitespaceError: [
        "define  the potential position<standard:/path>.\n",
    ],
}

_CHAR_ERROR_EXAMPLES: dict[type[parser_exceptions.DefineCharError], list[str]] = {
    # TODO: Make this into MissingWhitespaceError.
    parser_exceptions.InvalidCharacterError: [
        "define the potential position<standard:/path>{\n",
    ],
}

_CHAR_ERRORS: dict[str, type[parser_exceptions.DefineCharError]] = {
    "\ufeff": parser_exceptions.ByteOrderMarkError,
    "\r": parser_exceptions.CarriageReturnError,
}

_NEWLINE_OR_RBRACE_EXPECTED = {"NEWLINE", "RBRACE"}


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
    e: exceptions.UnexpectedCharacters,
    source: str,
    parse_fn: Callable[[str], Tree[Token]],
) -> type[parser_exceptions.DefineCharError] | None:
    """Classify a character rejected by the lexer in a syntax position."""
    char_class = _classify_invalid_char(e.char)
    if char_class is not None:
        return char_class

    if e.char == " ":
        if not _is_space_followed_only_by_whitespace(source, e.line, e.column):
            return None
        return parser_exceptions.TrailingWhitespaceError

    return e.match_examples(
        parse_fn,
        _CHAR_ERROR_EXAMPLES,
        use_accepts=True,
    )


def extract_char_error_from_token(
    e: exceptions.UnexpectedToken,
    source: str,
    file_path: str | os.PathLike[str] | None,
) -> parser_exceptions.DefineSyntaxError | None:
    r"""Extract a syntax error directly from an unexpected token, if possible.

    Name terminals accept any non-structural characters, so invalid
    characters can be absorbed into tokens in syntax positions — e.g.
    "\ufeffdefine" becomes AUTHORITY_PATH_SEGMENT instead of the "define"
    keyword. Only the first character matters because invalid characters
    mid-token parse successfully and are caught by the validator.
    """
    # The contextual lexer can surface spaces as UnexpectedToken instead of
    # UnexpectedCharacters depending on parser state. Handle both paths in
    # one place so whitespace diagnostics stay stable.
    token_str = str(e.token)
    if token_str:
        char_class = _classify_invalid_char(token_str[0])
        if char_class is not None:
            return char_class(
                e.get_context(source), e.line, e.column, token_str[0], file_path
            )

    if token_str and token_str.strip() == "" and "\n" not in token_str:
        if not _is_space_followed_only_by_whitespace(source, e.line, e.column):
            return parser_exceptions.UnexpectedWhitespaceError(
                e.get_context(source),
                e.line,
                e.column,
                e.token,
                file_path,
            )
        return parser_exceptions.TrailingWhitespaceError(
            e.get_context(source), e.line, e.column, " ", file_path
        )

    return None


def classify_token_error(
    e: exceptions.UnexpectedToken,
    source: str,
    parse_fn: Callable[[str], Tree[Token]],
) -> type[parser_exceptions.DefineTokenError] | None:
    """Classify a token error into a specific exception type."""
    error_line = source.split("\n")[e.line - 1]

    if "  " in error_line.lstrip():
        return parser_exceptions.UnexpectedWhitespaceError

    if e.token.type == "NAME_CONTENT":
        token_text = str(e.token)
        if (
            token_text.startswith("define the potential position<")
            and "DEFINE_THE_POSITION" in e.expected
        ):
            return parser_exceptions.GlobalPositionInLocalScopeError
        if token_text.startswith(
            "it may only contain dimension points where"
        ) and _NEWLINE_OR_RBRACE_EXPECTED.issubset(e.expected):
            return parser_exceptions.MultiplePositionConstraintBlocksError
        if "LESSTHAN" in e.expected:
            return parser_exceptions.MissingOpenAngleBracketError
        # Using accepts-based matching with ParserState can fail for contextual
        # lexer fallback tokens. State-only matching is enough here.
        return e.match_examples(
            parse_fn,
            _TOKEN_ERROR_EXAMPLES,
            use_accepts=False,
        )

    # Local positions are only valid before "it happens when" in an action
    # block. If we see one when only line-break-or-close is legal, report
    # the specific ordering error instead of a generic missing close brace.
    if (
        e.token.type == "DEFINE_THE_POSITION"
        and e.expected == _NEWLINE_OR_RBRACE_EXPECTED
    ):
        return parser_exceptions.LocalPositionAfterTriggerError

    if (
        e.token.type == "IT_MAY_ONLY_CONTAIN_DIMENSION_POINTS_WHERE"
        and _NEWLINE_OR_RBRACE_EXPECTED.issubset(e.expected)
    ):
        return parser_exceptions.MultiplePositionConstraintBlocksError
    # The contextual lexer may tokenize this prefix as PATH_SEGMENT in this
    # parser state; keep the same classification in that case.
    if str(e.token) == "it" and _NEWLINE_OR_RBRACE_EXPECTED.issubset(e.expected):
        return parser_exceptions.MultiplePositionConstraintBlocksError

    if "DEFINE_THE_POSITION" in e.expected and str(e.token) == "define":
        return parser_exceptions.GlobalPositionInLocalScopeError

    if "MORETHAN" in e.expected:
        return parser_exceptions.MissingCloseAngleBracketError

    return e.match_examples(
        parse_fn,
        _TOKEN_ERROR_EXAMPLES,
        use_accepts=True,
    )


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
