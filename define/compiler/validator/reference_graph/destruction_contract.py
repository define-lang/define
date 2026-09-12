"""Semantic identities for destruction and Destruction Contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler import ast


@dataclass(frozen=True, slots=True, eq=False)
class SimultaneousDestruction:
    """The directly destroyed particle and its Simultaneous Transitive Destruction."""

    directly_destroyed_position: ast.PositionReference
    destroying_action: ast.GlobalTypedName
    is_automatic: bool


@dataclass(frozen=True, slots=True, eq=False)
class DestructionFact:
    """Identifies the destruction of one specific particle."""

    destruction: SimultaneousDestruction
    destroyed_position_in_destroyer: ast.PositionReference


@dataclass(eq=False, slots=True)
class PropagatedDestruction:
    """A destruction expressed through an action's contracted position."""

    destruction_fact: DestructionFact
    # The contracted origin, as a chained name within the action exposing it.
    contracted_position: ast.PositionReference


@dataclass
class DestructionContribution:
    """Additional destruction work known by one caller."""

    destruction_fact: DestructionFact
    position_in_caller: ast.PositionReference
    destructors: list[ast.ActionReference]
    positions: list[ast.PositionReference]


@dataclass
class DestructionConnection:
    """Contributions supplied or forwarded to one callee destruction."""

    callee_destruction: PropagatedDestruction
    contribution: DestructionContribution | None = None
    forwarded_destructions: list[PropagatedDestruction] = field(default_factory=list)
