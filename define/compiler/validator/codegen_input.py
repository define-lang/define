"""Validated action steps and their resolved execution and destruction information."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler import chained_name
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
    # Callees whose pending Guarantees were dropped. The Destructors their
    # callers recorded for them still run.
    guaranteed_particle_destructors: list[CalleeDestructorsReference] = msgspec.field(
        default_factory=list
    )


class CalleeDestructorsReference(msgspec.Struct):
    """The Destructors a caller recorded for one of its callees."""

    caller: ast.ActionReference
    # The callee's action chain from the caller's perspective.
    callee: chained_name.ActionReferenceTuple
    # Which of the caller's callees with that chain this is: 1 for the first,
    # 2 for the second, and so on, since the same action can be triggered
    # more than once there.
    occurrence: int


class GuaranteedParticleDestructors(msgspec.Struct):
    """The Destructors that still run for one of an action's callees when its Guarantees are dropped, as the action's final state has its particles."""

    # The callee's action chain from this action's perspective.
    callee: chained_name.ActionReferenceTuple
    # Which of this action's callees with that chain this is: 1 for the first,
    # 2 for the second, and so on.
    occurrence: int

    # Destructors of particles the callee created.
    destructors: list[ast.ActionReference]
    # Callees of the callee whose Guarantees are still pending in this action,
    # whose own callers' recorded Destructors also run.
    callee_destructors: list[CalleeDestructorsReference]


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
    # One entry for each of the action's callees whose Destructors run when
    # its Guarantees are dropped.
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
