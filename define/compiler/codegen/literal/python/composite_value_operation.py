"""Literal Python generation for composite Value Operations."""

from __future__ import annotations

import typing

from define.compiler.codegen.literal.python import operation_function, value_types

if typing.TYPE_CHECKING:
    from define.compiler.codegen.literal.python import naming, renderer
    from define.compiler.validator import codegen_input


def generate_composite_value_operation(
    composite: codegen_input.CompositeValueOperation,
    converter: naming.NameConverter,
) -> renderer.OperationFunction:
    """Build the template context for a composite Value Operation's function for one set of encodings."""
    view_python_types: list[str] = []
    for encoding in composite.encodings:
        view_python_types.append(value_types.encoding_python_value_type(encoding))
    return operation_function.generate_step_function(
        converter,
        converter.composite_value_operation_function_reference(
            composite.definition.typed_name, composite.encodings
        ),
        composite.definition.views,
        view_python_types,
        composite.steps,
    )
