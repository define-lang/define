"""Parser for Define language statements."""

from pathlib import Path

from lark import Lark, Token, Tree


class ByteOrderMarkError(Exception):
    """Raised when a byte-order mark is present in input."""


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
        )

    def parse(self, source: str) -> Tree[Token]:
        """Parse Define source code and return a parse tree."""
        if source.startswith("\ufeff"):
            raise ByteOrderMarkError("Byte-order marks are forbidden")

        return self._lark.parse(source)
