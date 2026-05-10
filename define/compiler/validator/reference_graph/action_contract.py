"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from define.compiler import ast


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    UNKNOWN = enum.auto()


@dataclass(frozen=True)
class PositionRequirement:
    """An automatically inferred requirement on a contracted position.

    A contracted position is an interface position, a child of an interface
    position, an implied quality, or a child of an implied quality.
    """

    required_state: PositionOccupancyState
    # Can be either a position reference or an action reference.
    inferred_from: ast.ChainedName
    enclosing_action: ast.ActionDefinition
    propagated_from: PositionRequirement | None = None

    def root_cause_action_name(self) -> str:
        """Walk the propagation chain to find the originating action's canonical name."""
        current = self
        while current.propagated_from is not None:
            current = current.propagated_from
        return current.enclosing_action.typed_name.source_typed_name

    def full_propagation_position_chain(self) -> ast.PositionReference:
        """Get the full chained name composed by walking propagated_from."""
        typed_names = list(self.inferred_from.typed_names)
        current = self.propagated_from
        while current is not None:
            typed_names.extend(current.inferred_from.typed_names)
            current = current.propagated_from
        return ast.PositionReference(
            location=self.inferred_from.location,
            typed_names=typed_names,
        )

    def propagated_from_locations(self) -> list[ast.SourceLocation]:
        """Collect source locations from the propagated_from chain."""
        chain: list[ast.SourceLocation] = []
        current = self.propagated_from
        while current is not None:
            chain.append(current.inferred_from.location)
            current = current.propagated_from
        return chain


@dataclass(frozen=True)
class PositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""

    caused_by: ast.PositionReference


@dataclass(frozen=True)
class EmptyGuarantee(PositionGuarantee):
    """The position is guaranteed to be empty after the action completes."""


@dataclass(frozen=True)
class OccupiedByExistingGuarantee(PositionGuarantee):
    """The position contains the same DP that was passed into another interface position."""

    origin_position: ast.PositionReference


@dataclass(frozen=True)
class OccupiedByNewGuarantee(PositionGuarantee):
    """The position contains a new DP created by the action."""

    qualities: frozenset[str]


@dataclass(frozen=True)
class UnknownGuarantee(PositionGuarantee):
    """The position's state could not be determined due to an error."""


@dataclass(frozen=True)
class ActionStatementsBlockContract:
    """Base contract for any block containing action statements."""

    guarantees: dict[tuple[str, ...], PositionGuarantee]


@dataclass(frozen=True)
class ActionContract(ActionStatementsBlockContract):
    """The automatically inferred requirements and guarantees for an action."""

    requirements: dict[tuple[str, ...], PositionRequirement]
    # TODO: Support triggering on chained names?
    trigger_position_name: str


@dataclass(frozen=True)
class PositionInitBlockContract(ActionStatementsBlockContract):
    """Contract for a position initialization block."""
