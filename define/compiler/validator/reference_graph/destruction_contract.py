"""Semantic identities for destruction and Destruction Contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from define.compiler import ast


class SimultaneousDestruction(msgspec.Struct, frozen=True, eq=False):
    """The directly destroyed particle and its Simultaneous Transitive Destruction."""

    directly_destroyed_position: ast.PositionReference
    destroying_action: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]]
    is_automatic: bool


class DestructionFact(msgspec.Struct, frozen=True, eq=False):
    """Identifies the destruction of one specific particle."""

    destruction: SimultaneousDestruction
    destroyed_position_in_destroyer: ast.PositionReference


class PropagatedDestruction(msgspec.Struct, eq=False):
    """A destruction expressed through an action's contracted position."""

    destruction_fact: DestructionFact
    # The contracted origin, as a chained name within the action exposing it.
    contracted_position: ast.PositionReference


class DestructionContribution(msgspec.Struct):
    """Additional destruction work known by one caller."""

    destruction_fact: DestructionFact
    position_in_caller: ast.PositionReference
    destructors: list[ast.ActionReference]
    positions: list[ast.PositionReference]


class DestructionConnection(msgspec.Struct):
    """Contributions supplied or forwarded to one callee destruction."""

    callee_destruction: PropagatedDestruction
    contribution: DestructionContribution | None = None
    forwarded_destructions: list[PropagatedDestruction] = msgspec.field(
        default_factory=list
    )
