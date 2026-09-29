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


class ValueSetting(msgspec.Struct):
    """A validated Value Setting Statement."""

    target_position: ast.PositionReference
    # The value type of both positions.
    value_type: ast.GlobalTypedNameReference


class LiteralValueSetting(ValueSetting):
    """A Value Setting Statement whose source is a literal."""

    # Already in the value's encoding, so code generation never parses it.
    value: str


class PositionValueSetting(ValueSetting):
    """A Value Setting Statement whose source is another position."""

    source_position: ast.PositionReference


class OperationArgument[LookedAt](msgspec.Struct):
    """What one interface view of an executed operation looks at."""

    interface_view: ast.ViewDefinition
    # A literal is already in the interface view's encoding, so code generation
    # never parses it.
    looking_at: LookedAt | str


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


class EncodingOperationCodegenInput(msgspec.Struct):
    """An Encoding Operation's source-ordered steps."""

    definition: ast.EncodingOperationDefinition
    steps: list[EncodingOperationStep]


class CodegenInput(msgspec.Struct):
    """Validated definitions and ordered steps for code generation."""

    definition_order: reference_graph_order.ReferenceGraphOrder
    actions: dict[str, ActionCodegenInput]
    encoding_operations: dict[str, EncodingOperationCodegenInput]
