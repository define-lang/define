"""Validated action steps and their resolved execution and destruction information."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler.graphs import reference_graph_order
    from define.compiler.validator.reference_graph import destruction_contract


# Repeated executions of the same action must remain distinct while nested
# Guarantees move with or disappear with their particles.
class ActionExecution(msgspec.Struct, eq=False):
    """An action execution with its caller's destruction connections."""

    action: ast.ActionReference
    destruction_connections: list[destruction_contract.DestructionConnection] = (
        msgspec.field(default_factory=list)
    )


class Destruction(msgspec.Struct):
    """Known Destructors, contract contributions, and particle destructions."""

    destructors: list[ast.ActionReference] = msgspec.field(default_factory=list)
    contract_destructions: list[destruction_contract.PropagatedDestruction] = (
        msgspec.field(default_factory=list)
    )
    positions: list[ast.PositionReference] = msgspec.field(default_factory=list)


type ActionStep = (
    ast.LocalPositionDefinition
    | ast.CreateParticleStatement
    | ast.MoveParticleStatement
    | ActionExecution
    | Destruction
)


class ActionCodegenInput(msgspec.Struct):
    """An action's source-ordered steps and exposed destruction contracts."""

    definition: ast.ActionDefinition
    steps: list[ActionStep]
    propagated_destructions: list[destruction_contract.PropagatedDestruction]


class CodegenInput(msgspec.Struct):
    """Validated definitions and ordered action steps for code generation."""

    definition_order: reference_graph_order.ReferenceGraphOrder
    actions: dict[str, ActionCodegenInput]
