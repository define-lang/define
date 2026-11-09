"""Writes the parser's Rust `ParserDiagnostics`, which creates the diagnostics in `define.compiler.errors.diagnostics` that the parser reports.

Each class in `_PARSER_DIAGNOSTICS` gets a `ParserDiagnostics` method that
takes the start and end positions of its location, then the rest of its fields,
which are integers or text.
"""

from __future__ import annotations

import pathlib
import sys

from define.compiler.errors import diagnostics
from define.compiler.parsing.rust_generators import (
    diagnostic_description,
    rust_renderer,
)

_PARSER_DIAGNOSTICS: tuple[type[diagnostics.Diagnostic], ...] = (
    diagnostics.IncorrectIndentationDiagnostic,
    diagnostics.TrailingWhitespaceDiagnostic,
    diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic,
    diagnostics.MissingSpaceBeforeCommentAfterBraceDiagnostic,
    diagnostics.MissingNewlineAtEndOfFileDiagnostic,
    diagnostics.SpaceBeforeOpenAngleBracketDiagnostic,
    diagnostics.ByteOrderMarkInCommentDiagnostic,
    diagnostics.ControlCharacterInCommentDiagnostic,
    diagnostics.InvisibleCharacterInCommentDiagnostic,
    diagnostics.MissingTerminatorAtEndOfLineDiagnostic,
)


def main():
    """Write the Rust parser diagnostics to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = rust_renderer.ParserDiagnosticsDescription(
        module_name=diagnostics.__name__,
        diagnostics=[
            diagnostic_description.describe_diagnostic(cls)
            for cls in _PARSER_DIAGNOSTICS
        ],
    )
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_parser_diagnostics(description),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
