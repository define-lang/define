"""Validated action steps and their resolved execution and destruction information."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import msgspec

from define.compiler import ast

if TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import chained_name
    from define.compiler.graphs import reference_graph_order
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


class EncodedLiteral(msgspec.Struct):
    """A literal's content, validated and in the encoding that its use requires."""

    encoding: ast.GlobalTypedNameReference
    content: str


class ValueSetting(msgspec.Struct):
    """A validated Value Setting Statement."""

    target_position: ast.PositionReference
    # The value quality of both positions.
    value_quality: ast.GlobalTypedNameReference


@final
class LiteralValueSetting(ValueSetting):
    """A Value Setting Statement whose source is a literal."""

    value: EncodedLiteral


@final
class PositionValueSetting(ValueSetting):
    """A Value Setting Statement whose source is another position."""

    source_position: ast.PositionReference


class OperationArgument[LookedAt](msgspec.Struct):
    """What one interface view of an executed operation looks at."""

    interface_view: ast.InterfaceViewDefinition
    looking_at: LookedAt | EncodedLiteral


# What runs when the program runs: an Encoding Operation, by its name, or a
# composite Value Operation for one set of encodings.
type RuntimeOperation = (
    ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    | CompositeValueOperation
)


@final
class ActionOperationExecution(msgspec.Struct):
    """A validated Operation Execution Statement in an action."""

    operation: ast.GlobalTypedNameReference
    # The statement's arguments, in the order of the executed Value
    # Operation's interface views.
    operation_arguments: list[OperationArgument[ast.PositionReference]]
    # What executing the Value Operation runs for the encodings of the
    # positions that the arguments look at.
    runtime_operation: RuntimeOperation
    # In the order of the runtime operation's interface views.
    arguments: list[OperationArgument[ast.PositionReference]]


class OperationExecution(msgspec.Struct):
    """An execution in an Encoding Operation or in a composite Value Operation."""

    runtime_operation: RuntimeOperation
    # In the order of the runtime operation's interface views.
    arguments: list[OperationArgument[ast.LocalTypedNameReference]]

    def arguments_for[LookedAtT](
        self, execution_arguments: Sequence[OperationArgument[LookedAtT]]
    ) -> list[OperationArgument[LookedAtT]]:
        """Return this execution's arguments for one execution of a Value Operation, whose arguments are ``execution_arguments``.

        This must be what executing the Value Operation runs, so its arguments
        look at the Value Operation's interface views, or at literals in its
        statements.
        """
        looked_at_by_view: dict[str, LookedAtT | EncodedLiteral] = {}
        for argument in execution_arguments:
            looked_at_by_view[argument.interface_view.typed_name.source_typed_name] = (
                argument.looking_at
            )
        arguments: list[OperationArgument[LookedAtT]] = []
        for argument in self.arguments:
            looking_at = argument.looking_at
            if isinstance(looking_at, EncodedLiteral):
                arguments.append(
                    OperationArgument(
                        interface_view=argument.interface_view, looking_at=looking_at
                    )
                )
            else:
                arguments.append(
                    OperationArgument(
                        interface_view=argument.interface_view,
                        looking_at=looked_at_by_view[looking_at.source_typed_name],
                    )
                )
        return arguments


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

# A step of an Encoding Operation that does not execute the computer
# operation, or of a composite Value Operation.
type OperationStep = (
    ast.LocalViewDefinition | OperationExecution | ast.ViewSettingStatement
)


class ActionCodegenInput(msgspec.Struct):
    """An action's source-ordered steps and exposed destruction contracts."""

    definition: ast.ActionDefinition
    steps: list[ActionStep]
    destruction_contracts: list[destruction_contract.DestructionContract]
    # One entry for each of the action's contracted positions where
    # Destructors run for what it left.
    guaranteed_particle_destructors: list[GuaranteedParticleDestructors]


class EncodingOperationCodegenInput(msgspec.Struct):
    """An Encoding Operation's body: its source-ordered steps, or the computer operation that is its only statement."""

    definition: ast.EncodingOperationDefinition
    body: list[OperationStep] | ast.ComputerOperationExecutionStatement


class CompositeValueOperation(msgspec.Struct):
    """A composite Value Operation for one set of encodings: its source-ordered steps, with an Encoding Operation chosen for each execution for those encodings."""

    definition: ast.ValueOperationDefinition
    # The encoding of each of the Value Operation's interface views, keyed by
    # the view's source typed name.
    view_encodings: dict[str, ast.GlobalTypedNameReference]
    steps: list[OperationStep]

    def encodings(self) -> list[ast.GlobalTypedNameReference]:
        """Return the encodings of the Value Operation's interface views, in their order."""
        encodings: list[ast.GlobalTypedNameReference] = []
        for view in self.definition.views:
            encodings.append(self.view_encodings[view.typed_name.source_typed_name])
        return encodings


class CodegenInput(msgspec.Struct):
    """Validated definitions and ordered steps for code generation."""

    definition_order: reference_graph_order.ReferenceGraphOrder
    actions: dict[str, ActionCodegenInput]
    encoding_operations: dict[str, EncodingOperationCodegenInput]
    # Each value quality's one associated encoding, keyed by the value quality's
    # full typed name.
    value_encodings: dict[str, ast.GlobalTypedNameReference]
    # The composite Value Operations of each Value Operation that has any, one
    # for each set of encodings that executions of it look at, keyed by the
    # Value Operation's full typed name, in the order of their encodings.
    composite_value_operations: dict[str, list[CompositeValueOperation]]
