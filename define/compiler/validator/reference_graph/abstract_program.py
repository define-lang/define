"""The abstract program that reference graph validation produces and association resolution resolves to concrete code, with the step types that the concrete program shares."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import msgspec

if TYPE_CHECKING:
    from define.compiler import ast, chained_name
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )


# Repeated executions of the same action must remain distinct while nested
# Guarantees move with or disappear with their particles.
@final
class ActionExecution(msgspec.Struct, eq=False):
    """An action execution with its caller's destruction connections."""

    action: ast.ActionReference
    destruction_connections: list[destruction_contract.DestructionConnection] = (
        msgspec.field(default_factory=list)
    )


@final
class Destruction(msgspec.Struct):
    """A Simultaneous Transitive Destruction the action performs."""

    contribution: destruction_contract.DestructionContribution


class GuaranteedParticleDestructors(msgspec.Struct):
    """What runs when what an action left at and below one of its contracted positions is destroyed without being applied."""

    # Named as action_contract.GuaranteedPosition.position names positions.
    position_in_action: chained_name.PositionReferenceTuple
    # Destructors of the particle the action left there.
    destructors: list[ast.GlobalTypedNameReference]
    # What also runs for what the action left in its child positions.
    for_child_positions: list[destruction_contract.RunGuaranteedParticleDestructors]


class ValueSetting(msgspec.Struct):
    """A validated Value Setting Statement."""

    target_position: ast.PositionReference
    # The value quality of both positions.
    value_quality: ast.GlobalTypedNameReference


@final
class PositionValueSetting(ValueSetting):
    """A Value Setting Statement whose source is another position."""

    source_position: ast.PositionReference


class Argument[ViewT: ast.ViewDefinition, LookedAtT](msgspec.Struct):
    """What one view of an executed Value Operation or logical operation looks at."""

    interface_view: ViewT
    looking_at: LookedAtT


@final
class ActionOperationExecution(msgspec.Struct):
    """A validated Operation Execution Statement in an action."""

    operation: ast.GlobalTypedNameReference
    value_operation: ast.ValueOperationDefinition
    # In the order of the Value Operation's interface views.
    arguments: list[
        Argument[ast.InterfaceViewDefinition, ast.PositionReference | ast.Literal]
    ]
    # The value quality of each position that an argument looks at, keyed by
    # the source typed name of the interface view that looks at it.
    looked_at_value_qualities: dict[str, ast.GlobalTypedNameReference]


@final
class LiteralValueSetting(ValueSetting):
    """A Value Setting Statement whose source is a literal."""

    literal: ast.Literal


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


class AbstractAction(msgspec.Struct):
    """An action's source-ordered steps and exposed destruction contracts, before association resolution."""

    definition: ast.ActionDefinition
    steps: list[ActionStep]
    destruction_contracts: list[destruction_contract.DestructionContract]
    # One entry for each of the action's contracted positions where
    # Destructors run for what it left.
    guaranteed_particle_destructors: list[GuaranteedParticleDestructors]


class LogicalOperationExecution(msgspec.Struct):
    """A validated Logical Operation Execution Statement in a Value Operation."""

    logical_operation: ast.GlobalTypedNameReference
    # In the order of the logical operation's views.
    arguments: list[
        Argument[ast.LogicalOperationViewDefinition, ast.LocalTypedNameReference]
    ]


class ValueOperationExecution(msgspec.Struct):
    """A validated Operation Execution Statement in a Value Operation."""

    value_operation: ast.ValueOperationDefinition
    # The statement's name of the executed Value Operation, where diagnostics
    # about the execution are reported.
    operation: ast.GlobalTypedNameReference
    # In the order of the executed Value Operation's interface views.
    arguments: list[
        Argument[ast.InterfaceViewDefinition, ast.LocalTypedNameReference | ast.Literal]
    ]


# What a Value Operation does, independent of the encodings of the views that
# an execution of it looks at.
type ValueOperationStep = (
    ast.LocalViewDefinition
    | ast.ViewSettingStatement
    | LogicalOperationExecution
    | ValueOperationExecution
)


class AbstractValueOperation(msgspec.Struct):
    """A valid Value Operation's steps, before association resolution."""

    definition: ast.ValueOperationDefinition
    steps: list[ValueOperationStep]


# What reference graph validation hands to association resolution for one
# definition. Logical operations and value qualities need nothing from
# validation but their definitions.
type AbstractDefinition = (
    AbstractAction
    | AbstractValueOperation
    | ast.LogicalOperationDefinition
    | ast.ValueDefinition
)
