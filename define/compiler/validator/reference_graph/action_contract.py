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
    # The chained name at the line of source where this action inferred the
    # requirement.
    #
    # If this is a requirement imposed directly by this action,
    # this contains the full chained name used in the statement that imposed
    # the requirement (like `position<iface>::position</x>` for
    # `create a dimension point in position<iface>::position</x>.`)
    #
    # If this is a requirement that has been propagated from a called
    # action, then it contains only the prefix of the chain that is unique
    # within this action. For example, imagine we trigger an action via
    # `position<iface>::action</inner>::position<run>`, and it includes
    # a requirement on action</inner>::position<item>. This will contain
    # just `position<iface>::action</inner>` (which is why it is a ChainedName
    # and not a PositionReference).
    inferred_from: ast.ChainedName
    enclosing_quality: ast.QualityDefinition
    propagated_from: PositionRequirement | None = None

    def root_cause_quality(self) -> ast.QualityDefinition:
        """Return the quality definition that originally inferred this requirement."""
        current = self
        while current.propagated_from is not None:
            current = current.propagated_from
        return current.enclosing_quality

    def root_cause_quality_name(self) -> str:
        """Return the canonical name of the quality that originally inferred this requirement."""
        return self.root_cause_quality().typed_name.source_typed_name

    def full_propagation_position_chain(self) -> ast.PositionReference:
        """Get the full chained name composed by walking propagated_from."""
        if self.propagated_from is None:
            if not isinstance(self.inferred_from, ast.PositionReference):
                raise TypeError(
                    f"originating requirement's inferred_from must be a PositionReference, got {type(self.inferred_from).__name__}"
                )
            return self.inferred_from
        inner_full = self.propagated_from.full_propagation_position_chain()
        return inner_full.in_caller(self.inferred_from)

    def propagated_from_locations(self) -> list[ast.SourceLocation]:
        """Locations of intermediate propagation steps, ordered outer to inner."""
        locations: list[ast.SourceLocation] = []
        current = self.propagated_from
        while current is not None:
            locations.append(current.inferred_from.location)
            current = current.propagated_from
        return locations


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

    qualities: list[ast.GlobalTypedNameReference]


@dataclass(frozen=True)
class UnknownGuarantee(PositionGuarantee):
    """The position's state could not be determined due to an error."""


GuaranteePair = tuple[tuple[str, ...], PositionGuarantee]


@dataclass(frozen=True)
class ActionStatementsBlockContract:
    """Base contract for any block containing action statements."""

    requirements: dict[tuple[str, ...], PositionRequirement]
    guarantees: list[GuaranteePair]


@dataclass(frozen=True)
class ActionContract(ActionStatementsBlockContract):
    """The automatically inferred requirements and guarantees for an action."""

    # TODO: Support triggering on chained names?
    trigger_position_name: str


@dataclass(frozen=True)
class PositionInitBlockContract(ActionStatementsBlockContract):
    """Contract for a position initialization block."""
