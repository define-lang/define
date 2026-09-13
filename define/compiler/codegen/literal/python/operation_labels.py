"""Trace labels for generated particle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen.literal.python import template_context

if TYPE_CHECKING:
    from define.compiler import ast

_OPERATION_NAMES = {
    template_context.StatementKind.CREATE_PARTICLE: "create",
    template_context.StatementKind.MOVE_PARTICLE: "move",
    template_context.StatementKind.DESTROY_PARTICLE: "destroy",
}


def operation_label(
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    kind: template_context.StatementKind,
    position: ast.PositionReference,
    destination: ast.PositionReference | None = None,
) -> str:
    """Format the trace label for a particle operation."""
    position_name = _trace_position_name(position)
    if destination is not None:
        position_name += ", " + _trace_position_name(destination)
    operation = _OPERATION_NAMES[kind]
    action_name = action.name_content.path.name.removeprefix("/")
    return f"{action_name}.{operation}({position_name})"


def _trace_position_name(position: ast.PositionReference) -> str:
    return "::".join(name.name_content.source_name for name in position.typed_names)
