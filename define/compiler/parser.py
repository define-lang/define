"""Parser for Define language statements."""

import os
from pathlib import Path

from lark import Lark, Token, Tree, exceptions

from define.compiler import parser_error_classification, parser_exceptions

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


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

    def parse(
        self, source: str, file_path: str | os.PathLike[str] | None = None
    ) -> Tree[Token]:
        """Parse Define source code and return a parse tree.

        file_path is only used for error messages.
        """
        try:
            return self._lark.parse(source)
        except exceptions.UnexpectedCharacters as e:
            exc_class = parser_error_classification.classify_char_error(
                e, source, self._lark.parse
            )
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
            token_error = parser_error_classification.extract_char_error_from_token(
                e, source, file_path
            )
            if token_error is not None:
                raise token_error from e
            exc_class = parser_error_classification.classify_token_error(
                e, source, self._lark.parse
            )
            if exc_class is not None:
                raise exc_class(
                    e.get_context(source),
                    e.line,
                    e.column,
                    e.token,
                    file_path,
                ) from e
            raise

    def parse_file(self, path: os.PathLike[str]) -> tuple[Tree[Token], str]:
        """Parse a Define source file and return the parse tree and source text."""
        try:
            with open(path, encoding="utf-8", newline="") as f:
                source = f.read()
        except UnicodeDecodeError as e:
            raw = Path(path).read_bytes()
            raise parser_error_classification.make_invalid_encoding_error(
                raw, e, path
            ) from e
        return self.parse(source, file_path=path), source
