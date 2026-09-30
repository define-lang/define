"""Trace labels for generated particle operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen.literal.python import template_context, value_types
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from define.compiler import ast

_OPERATION_NAMES = {
    template_context.StatementKind.CREATE_PARTICLE: "create",
    template_context.StatementKind.MOVE_PARTICLE: "move",
    template_context.StatementKind.DESTROY_PARTICLE: "destroy",
    template_context.StatementKind.SET_VALUE_FROM: "set_value",
}


def operation_label(
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    kind: template_context.StatementKind,
    position: ast.PositionReference,
    destination: ast.PositionReference | None = None,
) -> str:
    """Format the trace label for a particle operation."""
    arguments = _trace_position_name(position)
    if destination is not None:
        arguments += ", " + _trace_position_name(destination)
    return _label(action, _OPERATION_NAMES[kind], arguments)


def literal_value_operation_label(
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    position: ast.PositionReference,
    value: str,
) -> str:
    """Format the trace label for setting a value from a literal."""
    return _label(action, "set_value", f"{_trace_position_name(position)}, {value}")


def operation_execution_label(
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    execution: codegen_input.ActionOperationExecution,
) -> str:
    """Format the trace label for executing an operation, with what each interface view looks at."""
    arguments: list[str] = [execution.operation.full_typed_name]
    for argument in execution.arguments:
        looking_at = argument.looking_at
        if isinstance(looking_at, codegen_input.EncodedLiteral):
            arguments.append(value_types.python_literal(looking_at))
        else:
            arguments.append(_trace_position_name(looking_at))
    return _label(action, "execute", ", ".join(arguments))


def _label(
    action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    operation: str,
    arguments: str,
) -> str:
    action_name = action.name_content.path.name.removeprefix("/")
    return f"{action_name}.{operation}({arguments})"


def _trace_position_name(position: ast.PositionReference) -> str:
    return "::".join(name.name_content.source_name for name in position.typed_names)
