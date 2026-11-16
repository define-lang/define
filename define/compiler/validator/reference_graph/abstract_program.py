"""The parts of a validated program that are the same before and after association resolution."""

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
