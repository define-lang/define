"""Parser for Define language statements."""

import os
from pathlib import Path

import regex
from lark import Lark, Token, Tree, exceptions

from define.compiler import parser_exceptions

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"

_TOKEN_ERROR_EXAMPLES: dict[type[parser_exceptions.DefineTokenError], list[str]] = {
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
    ],
    parser_exceptions.InvalidAuthorityPathError: [
        "define the potential position<example.com/.hidden:my_lib:/path>.\n",
        "define the potential position<example.com/ba<d:my_lib:/path>.\n",
        "define the potential position<mymv:example.com/.hidden:my_lib:/path>.\n",
    ],
    parser_exceptions.InvalidGlobalNamePathError: [
        "define the potential position<standard:path>.\n",
        "define the potential position<standard:/a//b>.\n",
        "define the potential position<standard:/bad-name>.\n",
        "define the potential position<standard:/bad~name>.\n",
        "define the potential position<standard:/2bad>.\n",
        "define the potential position<mymv:example.com:my_lib:/bad-name>.\n",
        "define the potential position<mymv:example.com:my_lib:/a/bad-name>.\n",
        "define the potential position<my_name>.\n",
    ],
    parser_exceptions.InvalidAuthorityDomainError: [
        "define the potential position<-example.com:my_lib:/path>.\n",
        "define the potential position<.example.com:my_lib:/path>.\n",
        "define the potential position<example.com-:my_lib:/path>.\n",
        "define the potential position<example.com.:my_lib:/path>.\n",
        "define the potential position<x:my_lib:/path>.\n",
        "define the potential position<mymv:.example.com:my_lib:/path>.\n",
        "define the potential position<mymv:-example.com:my_lib:/path>.\n",
        "define the potential position<mymv:a:my_lib:/path>.\n",
        "define the potential position<mymv:example.com.:my_lib:/path>.\n",
        "define the potential position<mymv:example.com-:my_lib:/path>.\n",
    ],
    parser_exceptions.InvalidUniverseError: [
        "define the potential position<example.com:_mylib:/path>.\n",
        "define the potential position<example.com:mylib_:/path>.\n",
        "define the potential position<example.com:x:/path>.\n",
        "define the potential position<example.com:m\u00fclib:/path>.\n",
        "define the potential position<mymv:example.com:_my_lib:/path>.\n",
        "define the potential position<mymv:example.com:my_lib_:/path>.\n",
        "define the potential position<mymv:example.com:x:/path>.\n",
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
    parser_exceptions.InvalidCharacterError: [
        "define the potential position<standard:/bad!name>.\n",
        "define the potential position<mymv:example.com:my_lib:/bad!name>.\n",
        "define the potential position<mymv:example.com:my_lib:/a/bad!name>.\n",
    ],
}

_CHAR_ERRORS: dict[str, type[parser_exceptions.DefineCharError]] = {
    "\ufeff": parser_exceptions.ByteOrderMarkError,
    "\r": parser_exceptions.CarriageReturnError,
}


_IDENTIFIER_TERMINALS = frozenset(
    {"MULTIVERSE_NAME", "AUTHORITY_DOMAIN", "UNIVERSE_NAME"}
)

# Matches the structure of a 4-part FQUN (multiverse:authority:universe:/path)
# from the error position. Based on the MULTIVERSE_NAME terminal lookahead
# in grammar.lark.
_MULTIVERSE_CONTEXT = regex.compile(r"[^:>]*:[^:>]*:[^:>]*:/")


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
        self, e: exceptions.UnexpectedCharacters
    ) -> type[parser_exceptions.DefineCharError] | None:
        """Classify a character error into a specific exception type."""
        char_class = _CHAR_ERRORS.get(e.char)
        if char_class is not None:
            return char_class

        if e.char.isupper():
            return parser_exceptions.UppercaseNotAllowedError

        if e.char == " ":
            return parser_exceptions.TrailingWhitespaceError

        if ord(e.char) < 0x20 or ord(e.char) == 0x7F:
            return parser_exceptions.ControlCharacterError

        if "\ud800" <= e.char <= "\udfff":
            return parser_exceptions.InvalidEncodingError

        if ord(e.char) > 0x7F:
            return parser_exceptions.InvalidCharacterError

        return e.match_examples(
            self._lark.parse,
            _CHAR_ERROR_EXAMPLES,
            use_accepts=True,
        )

    def _classify_token_error(
        self, e: exceptions.UnexpectedToken, source: str
    ) -> type[parser_exceptions.DefineTokenError] | None:
        """Classify a token error into a specific exception type."""
        # Consecutive spaces are never valid in the grammar, but
        # match_examples can't distinguish them from incomplete statements.
        error_line = source.split("\n")[e.line - 1]
        if "  " in error_line:
            return parser_exceptions.UnexpectedWhitespaceError

        # A DOT after a PATH_SEGMENT is ambiguous to match_examples: both
        # "<standard:/bad.name>.\n" (invalid path) and "<standard:/path.\n"
        # (missing close bracket) produce the same parser state. We
        # disambiguate by checking whether the dot is the statement
        # terminator (last character on the line). If not, it must be an
        # invalid character inside the path.
        if e.token.type == "DOT" and e.token_history:
            prev = e.token_history[-1]
            if prev.type == "PATH_SEGMENT" and e.column < len(error_line):
                return parser_exceptions.InvalidGlobalNamePathError

        # match_examples can't distinguish multiverse name errors from
        # authority domain errors because single-char names share LALR
        # states across both forms. Detect the 4-part FQUN structure
        # from the error position using the MULTIVERSE_NAME lookahead.
        if _IDENTIFIER_TERMINALS.issubset(e.expected) and _MULTIVERSE_CONTEXT.match(
            error_line[e.column - 1 :]
        ):
            return parser_exceptions.InvalidMultiverseError

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
            exc_class = self._classify_char_error(e)
            if exc_class is not None:
                raise exc_class(
                    e.get_context(source), e.line, e.column, e.char, file_path
                ) from e
            raise
        except exceptions.UnexpectedToken as e:
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
