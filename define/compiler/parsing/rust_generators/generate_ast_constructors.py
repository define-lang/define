"""Writes the `AstBuilder` constructors of the parser's Rust AST types."""

from __future__ import annotations

import pathlib
import sys

from define.compiler import ast
from define.compiler.parsing.rust_generators import ast_description, rust_renderer


def main():
    """Write the Rust code to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_ast_constructors(ast_description.describe(ast)),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
