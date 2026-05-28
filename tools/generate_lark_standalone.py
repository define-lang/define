"""Generate a Lark standalone parser module.

Usage:
    generate_lark_standalone.py <grammar_file>
"""

import sys
from pathlib import Path

import lark
from lark.tools import standalone


def main():
    """Generate a standalone parser from a grammar file."""
    if len(sys.argv) != 2:
        raise ValueError("Usage: generate_lark_standalone.py <grammar_file>")

    grammar_path = Path(sys.argv[1])
    grammar = grammar_path.read_text(encoding="utf-8")

    parser = lark.Lark(
        grammar,
        parser="lalr",
        regex=True,
        # The transformer derives SourceLocation directly from each Tree's
        # transformed children (Tokens carry line/column from the lexer;
        # already-transformed ASTNode children carry .location), so we do
        # not need lark's PropagatePositions to populate Tree.meta. Avoiding
        # that pass is a measurable speedup -- it was the single hottest
        # function in the profile.
        propagate_positions=False,
        start="start",
    )

    output_path = Path("lark_parser.py")
    with output_path.open("w", encoding="utf-8") as output_file:
        standalone.gen_standalone(
            parser,
            out=output_file,
        )


if __name__ == "__main__":
    main()
