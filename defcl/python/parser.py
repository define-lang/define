"""Parser for Define Configuration Language (DCL) files."""

import os
from functools import cached_property
from pathlib import Path

import lark

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


class Parser:
    """Parser for DCL files using Lark."""

    @cached_property
    def _parser(self) -> lark.Lark:
        return lark.Lark(_GRAMMAR_PATH.read_text(), parser="lalr", start="start")

    def parse(self, text: str) -> lark.Tree[lark.Token]:
        """Parse DCL text and return the parse tree."""
        return self._parser.parse(text)

    def parse_file(self, path: str | os.PathLike[str]) -> lark.Tree[lark.Token]:
        """Parse a DCL file and return the parse tree."""
        with open(path, encoding="utf-8", newline="") as f:
            return self.parse(f.read())
