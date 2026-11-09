"""Writes the parser's Rust `SyntaxErrors`, which creates the syntax errors in `define.compiler.errors.syntax_errors`.

Each syntax error class that the parser can report, which is every subclass of
`DefineSyntaxError` that is not itself a base class, gets a `SyntaxErrors`
method that takes the start and end positions of its location, then the rest
of its fields.
"""

from __future__ import annotations

import pathlib
import sys

from define.compiler.errors import syntax_errors
from define.compiler.parsing.rust_generators import (
    diagnostic_description,
    rust_renderer,
)


def _syntax_error_classes() -> list[type[syntax_errors.DefineSyntaxError]]:
    namespace: dict[str, object] = dict(vars(syntax_errors))
    classes: list[type[syntax_errors.DefineSyntaxError]] = []
    for value in namespace.values():
        if (
            isinstance(value, type)
            and issubclass(value, syntax_errors.DefineSyntaxError)
            and value.__module__ == syntax_errors.__name__
            and not value.__subclasses__()
        ):
            classes.append(value)
    return classes


def main():
    """Write the Rust syntax errors to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = rust_renderer.SyntaxErrorsDescription(
        module_name=syntax_errors.__name__,
        syntax_errors=[
            diagnostic_description.describe_diagnostic(cls)
            for cls in _syntax_error_classes()
        ],
    )
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_syntax_errors(description), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
