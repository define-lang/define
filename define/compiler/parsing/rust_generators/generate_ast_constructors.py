"""Writes the `AstBuilder` constructors of the parser's Rust AST types."""

from __future__ import annotations

import sys

from define.compiler import ast
from define.compiler.parsing.rust_generators import (
    ast_description,
    rust_output,
    rust_renderer,
)


def main():
    """Write the Rust code to the path given as the first argument.

    The rustfmt program given as the second argument formats it.
    """
    output_path, rustfmt = sys.argv[1:]
    rust_output.write(
        output_path,
        rust_renderer.render_ast_constructors(ast_description.describe(ast)),
        rustfmt,
    )


if __name__ == "__main__":
    main()
