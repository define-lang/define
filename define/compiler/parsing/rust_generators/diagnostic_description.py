"""Descriptions of diagnostic classes for the Rust generators that create them."""

from __future__ import annotations

import inspect
import typing

from define.compiler.parsing.rust_generators import rust_names, rust_renderer

if typing.TYPE_CHECKING:
    from define.compiler.errors import diagnostics


# The type of each field's annotation, which is a string because the modules of
# diagnostic classes postpone the evaluation of their annotations.
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


def describe_diagnostic(
    cls: type[diagnostics.Diagnostic],
) -> rust_renderer.ParserDiagnostic:
    """Describe a diagnostic class whose location comes first and whose other fields are integers or text."""
    location, *field_names = cls.__struct_fields__
    if (
        location != "location"
        or _annotation(cls, location) != "rendering.SourceLocation"
    ):
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
