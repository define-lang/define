"""Writes the parser's Rust `ParserDiagnostics`, which creates the diagnostics in `define.compiler.errors.diagnostics` that the parser reports.

Each class in `_PARSER_DIAGNOSTICS` gets a `ParserDiagnostics` method that
takes the start and end positions of its location, then the rest of its fields,
which are all integers.
"""

from __future__ import annotations

import inspect
import pathlib
import sys

from define.compiler.errors import diagnostics
from define.compiler.parsing.rust_generators import rust_names, rust_renderer

_PARSER_DIAGNOSTICS: tuple[type[diagnostics.Diagnostic], ...] = (
    diagnostics.IncorrectIndentationDiagnostic,
    diagnostics.TrailingWhitespaceDiagnostic,
    diagnostics.MissingSpaceBeforeCommentAfterTerminatorDiagnostic,
    diagnostics.MissingSpaceBeforeCommentAfterBraceDiagnostic,
    diagnostics.MissingNewlineAtEndOfFileDiagnostic,
    diagnostics.SpaceBeforeOpenAngleBracketDiagnostic,
)


def _annotation(cls: type, field: str) -> object:
    for base in cls.__mro__:
        annotations: dict[str, object] = inspect.get_annotations(base)
        if field in annotations:
            return annotations[field]
    raise ValueError(f"{cls.__name__}.{field} has no annotation")


def _describe_diagnostic(
    cls: type[diagnostics.Diagnostic],
) -> rust_renderer.ParserDiagnostic:
    location, *integer_fields = cls.__struct_fields__
    # The annotations are strings because diagnostics postpones their
    # evaluation.
    if location != "location" or _annotation(cls, location) != "ast.SourceLocation":
        raise ValueError(f"{cls.__name__} must have a location first")
    for field in integer_fields:
        annotation = _annotation(cls, field)
        if annotation != "int":
            raise ValueError(f"{cls.__name__}.{field} must be an int, not {annotation}")
    return rust_renderer.ParserDiagnostic(
        name=cls.__name__,
        snake_case_name=rust_names.snake_case_name(cls.__name__),
        integer_fields=integer_fields,
    )


def main():
    """Write the Rust parser diagnostics to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = rust_renderer.ParserDiagnosticsDescription(
        module_name=diagnostics.__name__,
        diagnostics=[_describe_diagnostic(cls) for cls in _PARSER_DIAGNOSTICS],
    )
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_parser_diagnostics(description),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
