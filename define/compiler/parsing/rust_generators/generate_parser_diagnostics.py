"""Writes the parser's Rust `ParserDiagnostics`, which creates the diagnostics in `define.compiler.errors.parser_diagnostics`.

Each diagnostic class in `define.compiler.errors.parser_diagnostics` gets a
`ParserDiagnostics` method that takes the start and end positions of its
location, then the rest of its fields, which are integers or text.
"""

from __future__ import annotations

import sys

from define.compiler.errors import diagnostics, parser_diagnostics
from define.compiler.parsing.rust_generators import (
    diagnostic_description,
    rust_output,
    rust_renderer,
)


def _parser_diagnostic_classes() -> list[type[diagnostics.Diagnostic]]:
    namespace: dict[str, object] = dict(vars(parser_diagnostics))
    classes: list[type[diagnostics.Diagnostic]] = []
    for value in namespace.values():
        if (
            isinstance(value, type)
            and issubclass(value, diagnostics.Diagnostic)
            and value.__module__ == parser_diagnostics.__name__
        ):
            classes.append(value)
    return classes


def _describe_parser_diagnostic(
    cls: type[diagnostics.Diagnostic],
) -> rust_renderer.ParserDiagnostic:
    # Only a load failure, which ends the parse, can have no location.
    if "location" not in cls.__struct_fields__:
        raise ValueError(f"{cls.__name__} must have a location")
    return diagnostic_description.describe_diagnostic(cls)


def main():
    """Write the Rust parser diagnostics to the path given as the first argument.

    The rustfmt program given as the second argument formats them.
    """
    output_path, rustfmt = sys.argv[1:]
    description = rust_renderer.ParserDiagnosticsDescription(
        module_name=parser_diagnostics.__name__,
        diagnostics=[
            _describe_parser_diagnostic(cls) for cls in _parser_diagnostic_classes()
        ],
    )
    rust_output.write(
        output_path, rust_renderer.render_parser_diagnostics(description), rustfmt
    )


if __name__ == "__main__":
    main()
