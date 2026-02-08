"""Parser using Lark grammar with transformer and semantic validation."""

from functools import cached_property
from pathlib import Path

import lark

from define.compiler.prototype import indenter


class Parser:
    """Parser for Define language with transformation and validation."""

    @cached_property
    def _parser(self) -> lark.Lark:
        """A Lark parser using the Define grammar."""
        grammar_path = Path(__file__).parent / "grammar.lark"
        return lark.Lark.open(
            str(grammar_path),
            parser="lalr",
            postlex=indenter.DefineIndenter(),
            start="start",
        )

    def parse(self, source: str) -> lark.Tree:
        """
        Parse source code into a parse tree.

        Args:
            source: Source code to parse

        Returns:
            Lark parse tree
        """
        return self._parser.parse(source)
