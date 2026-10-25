"""Writes the parser's Rust `ParserDiagnostics`, which creates the diagnostics in `define.compiler.errors.diagnostics` that the parser reports.

Each class in `_PARSER_DIAGNOSTICS` gets a `ParserDiagnostics` method that
takes the start and end positions of its location, then the rest of its fields,
which are integers or text.
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
    diagnostics.ByteOrderMarkInCommentDiagnostic,
    diagnostics.ControlCharacterInCommentDiagnostic,
    diagnostics.InvisibleCharacterInCommentDiagnostic,
    diagnostics.MissingTerminatorAtEndOfLineDiagnostic,
    diagnostics.OperationArgumentPositionDiagnostic,
    diagnostics.OperationArgumentViewDiagnostic,
)


# The type of each field's annotation, which is a string because diagnostics
# postpones the evaluation of its annotations.
_FIELD_TYPES: dict[object, rust_renderer.DiagnosticFieldType] = {
    "int": rust_renderer.DiagnosticFieldType.Integer(),
    "str": rust_renderer.DiagnosticFieldType.Text(),
}


def _annotation(cls: type, field: str) -> object:
    for base in cls.__mro__:
        annotations: dict[str, object] = inspect.get_annotations(base)
        if field in annotations:
            return annotations[field]
    raise ValueError(f"{cls.__name__}.{field} has no annotation")


def _describe_diagnostic(
    cls: type[diagnostics.Diagnostic],
) -> rust_renderer.ParserDiagnostic:
    location, *field_names = cls.__struct_fields__
    # The annotations are strings because diagnostics postpones their
    # evaluation.
    if location != "location" or _annotation(cls, location) != "ast.SourceLocation":
        raise ValueError(f"{cls.__name__} must have a location first")
    fields: list[rust_renderer.DiagnosticField] = []
    for field_name in field_names:
        annotation = _annotation(cls, field_name)
        field_type = _FIELD_TYPES.get(annotation)
        if field_type is None:
            raise ValueError(
                f"{cls.__name__}.{field_name} must be an int or a str, not {annotation}"
            )
        fields.append(
            rust_renderer.DiagnosticField(name=field_name, field_type=field_type)
        )
    return rust_renderer.ParserDiagnostic(
        name=cls.__name__,
        snake_case_name=rust_names.snake_case_name(cls.__name__),
        fields=fields,
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
