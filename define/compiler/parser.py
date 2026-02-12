"""Parser for Define language statements."""

import os
from pathlib import Path

from lark import Lark, Token, Tree, exceptions

from define.compiler import parser_exceptions

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"

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
    parser_exceptions.InvalidAuthorityPathError: [
        "define the potential position<example.com/ba<d:my_lib:/path>.\n",
    ],
    parser_exceptions.InvalidGlobalNamePathError: [
        "define the potential position<standard:path>.\n",
        "define the potential position<standard:/a//b>.\n",
        "define the potential position<my_name>.\n",
        "define the potential position<standard:/path> {\n"
        + "it may only contain dimension points where {\n"
        + "it has the position<child>.\n"
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


class Parser:
    """Parser for Define language source code."""

    _lark: Lark

    def __init__(self):
        """Initialize the parser with the Define grammar."""
        self._lark = Lark.open(
            str(_GRAMMAR_PATH),
            parser="lalr",
            propagate_positions=True,
            regex=True,
        )

    def _classify_char_error(
        self, e: exceptions.UnexpectedCharacters, source: str
    ) -> type[parser_exceptions.DefineCharError] | None:
        """Classify a character rejected by the lexer in a syntax position."""
        char_class = _classify_invalid_char(e.char)
        if char_class is not None:
            return char_class

        if e.char == " ":
            if not self._is_space_followed_only_by_whitespace(source, e.line, e.column):
                return None
            return parser_exceptions.TrailingWhitespaceError

        return e.match_examples(
            self._lark.parse,
            _CHAR_ERROR_EXAMPLES,
            use_accepts=True,
        )

    def _extract_char_error_from_token(
        self,
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
        if str(e.token) == " ":
            if not self._is_space_followed_only_by_whitespace(source, e.line, e.column):
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

        token_str = str(e.token)
        if not token_str:
            return None
        # When invalid bytes/characters are absorbed into broad name terminals,
        # the parse error points at the whole token; classify by first codepoint
        # here so users still get the precise character-level syntax error.
        char_class = _classify_invalid_char(token_str[0])
        if char_class is not None:
            return char_class(
                e.get_context(source), e.line, e.column, token_str[0], file_path
            )
        return None

    @staticmethod
    def _is_space_followed_only_by_whitespace(
        source: str, line: int, column: int
    ) -> bool:
        """Return whether the space is followed only by whitespace on its line."""
        error_line = source.split("\n")[line - 1]
        return not error_line[column:].strip()

    def _classify_token_error(
        self, e: exceptions.UnexpectedToken, source: str
    ) -> type[parser_exceptions.DefineTokenError] | None:
        """Classify a token error into a specific exception type."""
        error_line = source.split("\n")[e.line - 1]

        if "  " in error_line.lstrip():
            return parser_exceptions.UnexpectedWhitespaceError

        # A "define" token where only NEWLINE or RBRACE is expected means
        # something appeared after the trigger/action blocks. If the line
        # contains a local position definition, give a specific error;
        # otherwise fall through to match_examples (missing close brace).
        if (
            str(e.token).startswith("define")
            and e.expected == {"NEWLINE", "RBRACE"}
            and "define the position<" in error_line
        ):
            return parser_exceptions.LocalPositionAfterTriggerError

        if (
            str(e.token).startswith("define")
            and "define the potential position<" in error_line
            and "DEFINE_THE_POSITION" in e.expected
        ):
            return parser_exceptions.GlobalPositionInLocalScopeError

        if "MORETHAN" in e.expected:
            return parser_exceptions.MissingCloseAngleBracketError

        return e.match_examples(
            self._lark.parse,
            _TOKEN_ERROR_EXAMPLES,
            use_accepts=True,
        )

    def parse(
        self, source: str, file_path: str | os.PathLike[str] | None = None
    ) -> Tree[Token]:
        """Parse Define source code and return a parse tree.

        file_path is only used for error messages.
        """
        try:
            return self._lark.parse(source)
        except exceptions.UnexpectedCharacters as e:
            exc_class = self._classify_char_error(e, source)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(source), e.line, e.column, e.char, file_path
                ) from e
            if e.char == " ":
                raise parser_exceptions.UnexpectedWhitespaceError(
                    e.get_context(source), e.line, e.column, Token("", ""), file_path
                ) from e
            raise
        except exceptions.UnexpectedToken as e:
            token_error = self._extract_char_error_from_token(e, source, file_path)
            if token_error is not None:
                raise token_error from e
            exc_class = self._classify_token_error(e, source)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(source),
                    e.line,
                    e.column,
                    e.token,
                    file_path,
                ) from e
            raise

    @staticmethod
    def _get_invalid_unicode_context(
        raw: bytes, e: UnicodeDecodeError
    ) -> tuple[str, int, int, str]:
        """Extract context information from a UnicodeDecodeError."""
        before = raw[: e.start]
        line = before.count(b"\n") + 1
        last_newline = before.rfind(b"\n")
        column = e.start - last_newline
        context = raw[last_newline + 1 : e.start + 20]
        context_str = context.decode("utf-8", errors="replace")
        bad_byte = f"\\x{raw[e.start]:02x}"
        return context_str, line, column, bad_byte

    def parse_file(self, path: os.PathLike[str]) -> tuple[Tree[Token], str]:
        """Parse a Define source file and return the parse tree and source text."""
        try:
            with open(path, encoding="utf-8", newline="") as f:
                source = f.read()
        except UnicodeDecodeError as e:
            raw = Path(path).read_bytes()
            context_str, line, column, bad_byte = self._get_invalid_unicode_context(
                raw, e
            )
            raise parser_exceptions.InvalidEncodingError(
                context_str, line, column, bad_byte, path
            ) from e
        return self.parse(source, file_path=path), source
