"""Parser for Define language statements."""

import os
from pathlib import Path

from lark import Lark, Token, Tree

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
        return self._lark.parse(source)

    def parse_file(self, path: os.PathLike[str]) -> tuple[Tree[Token], str]:
        """Parse a Define source file and return the parse tree and source text."""
        with open(path, encoding="utf-8", newline="") as f:
            source = f.read()
        return self.parse(source), source
