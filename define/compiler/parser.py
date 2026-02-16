"""Parser for Define language statements."""

import os
from pathlib import Path

from lark import Lark, Token, Tree, exceptions

from define.compiler import parser_error_classification

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
            exc_class = parser_error_classification.classify_char_error(e, source)
            if exc_class is not None:
                raise exc_class.from_lark_exception(e, source, e.char, file_path) from e
            raise
        except exceptions.UnexpectedToken as e:
            parser_error_classification.raise_token_error(e, source, file_path)
            raise
