"""Validated action steps and their resolved execution and destruction information."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler import chained_name
    from define.compiler.graphs import reference_graph_order
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )


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
    # What runs for particles that callees left below the destroyed
    # particles and that this action never expanded.
    guaranteed_particle_destructors: list[
        destruction_contract.RunGuaranteedParticleDestructors
    ] = msgspec.field(default_factory=list)


class GuaranteedParticleDestructors(msgspec.Struct):
    """What runs when what an action left at and below one of its contracted positions is destroyed without being applied."""

    # From the action's perspective.
    position: ast.PositionReference
    # Named as action_contract.GuaranteedPosition.position names positions.
    position_in_action: chained_name.PositionReferenceTuple
    # Destructors of the particle the action left there.
    destructors: list[ast.GlobalTypedNameReference]
    # What also runs for what the action left in its child positions.
    for_child_positions: list[destruction_contract.RunGuaranteedParticleDestructors]


class EncodedLiteral(msgspec.Struct):
    """A literal's content, validated and in the encoding that its use requires."""

    # The full typed name of the encoding.
    encoding: str
    content: str


class ValueSetting(msgspec.Struct):
    """A validated Value Setting Statement."""

    target_position: ast.PositionReference
    # The value type of both positions.
    value_type: ast.GlobalTypedNameReference


class LiteralValueSetting(ValueSetting):
    """A Value Setting Statement whose source is a literal."""

    value: EncodedLiteral


class PositionValueSetting(ValueSetting):
    """A Value Setting Statement whose source is another position."""

    source_position: ast.PositionReference


class OperationArgument[LookedAt](msgspec.Struct):
    """What one interface view of an executed operation looks at."""

    interface_view: ast.ViewDefinition
    looking_at: LookedAt | EncodedLiteral


class ActionOperationExecution(msgspec.Struct):
    """A validated Operation Execution Statement in an action."""

    operation: ast.GlobalTypedNameReference
    # Executing a Value Operation runs the Encoding Operation that performs it.
    encoding_operation: ast.GlobalTypedNameReference
    # In the order of the executed operation's interface views.
    arguments: list[OperationArgument[ast.PositionReference]]


class EncodingOperationExecution(msgspec.Struct):
    """A validated Operation Execution Statement in an Encoding Operation."""

    encoding_operation: ast.GlobalTypedNameReference
    # In the order of the executed Encoding Operation's interface views.
    arguments: list[OperationArgument[ast.LocalTypedNameReference]]


type ActionStep = (
    ast.LocalPositionDefinition
    | ast.CreateParticleStatement
    | ast.MoveParticleStatement
    | LiteralValueSetting
    | PositionValueSetting
    | ActionExecution
    | Destruction
    | ActionOperationExecution
)

type EncodingOperationStep = (
    EncodingOperationExecution | ast.ComputerOperationExecutionStatement
)


class ActionCodegenInput(msgspec.Struct):
    """An action's source-ordered steps and exposed destruction contracts."""

    definition: ast.ActionDefinition
    steps: list[ActionStep]
    propagated_destructions: list[destruction_contract.PropagatedDestruction]
    # One entry for each of the action's contracted positions where
    # Destructors run for what it left.
    guaranteed_particle_destructors: list[GuaranteedParticleDestructors]


class EncodingOperationCodegenInput(msgspec.Struct):
    """An Encoding Operation's source-ordered steps."""

    definition: ast.EncodingOperationDefinition
    steps: list[EncodingOperationStep]


class CodegenInput(msgspec.Struct):
    """Validated definitions and ordered steps for code generation."""

    definition_order: reference_graph_order.ReferenceGraphOrder
    actions: dict[str, ActionCodegenInput]
    encoding_operations: dict[str, EncodingOperationCodegenInput]
