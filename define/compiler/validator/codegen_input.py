"""Validated action steps and their resolved execution and destruction information."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler.graphs import reference_graph_executor
    from define.compiler.validator.reference_graph import destruction_contract


@dataclass(slots=True)
class ActionExecution:
    """An action execution with its caller's destruction connections."""

    action: ast.ActionReference
    destruction_connections: list[destruction_contract.DestructionConnection] = field(
        default_factory=list
    )


@dataclass(slots=True)
class Destruction:
    """Known Destructors, contract contributions, and particle destructions."""

    destructors: list[ast.ActionReference] = field(default_factory=list)
    contract_destructions: list[destruction_contract.PropagatedDestruction] = field(
        default_factory=list
    )
    positions: list[ast.PositionReference] = field(default_factory=list)


type ActionStep = (
    ast.LocalPositionDefinition
    | ast.CreateParticleStatement
    | ast.MoveParticleStatement
    | ActionExecution
    | Destruction
)


@dataclass(slots=True)
class ActionCodegenInput:
    """An action's source-ordered steps and exposed destruction contracts."""

    definition: ast.ActionDefinition
    steps: list[ActionStep]
    propagated_destructions: list[destruction_contract.PropagatedDestruction]


@dataclass(slots=True)
class CodegenInput:
    """Validated definitions and ordered action steps for code generation."""

    definition_order: reference_graph_executor.ReferenceGraphOrder
    actions: dict[str, ActionCodegenInput]
