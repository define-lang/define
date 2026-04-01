"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler import ast


class PositionOccupancyState(enum.Enum):
    """The occupancy state of an interface position."""

    EMPTY = enum.auto()
    OCCUPIED = enum.auto()
    UNKNOWN = enum.auto()


@dataclass(frozen=True)
class InterfacePositionRequirement:
    """An automatically inferred requirement on an action interface position."""

    required_state: PositionOccupancyState
    inferred_from: (
        ast.PositionReference
    )  # TODO: Actually can also be an action reference.
    enclosing_action: ast.ActionDefinition
    propagated_from: InterfacePositionRequirement | None = None

    def root_cause_action_name(self) -> str:
        """Walk the propagation chain to find the originating action's canonical name."""
        current = self
        while current.propagated_from is not None:
            current = current.propagated_from
        return current.enclosing_action.typed_name.source_typed_name

    def resolved_chained_name(self, caller_fqun: ast.Fqun) -> str:
        """Return the requirement's chained name resolved for the caller's FQUN context.

        Walks the propagation chain, resolving each level's elements against
        its enclosing action's FQUN. Uses source form for same-FQUN elements
        and canonical form for cross-FQUN elements.
        """
        # Each propagation level's inferred_from.chain contains only that
        # level's prefix (e.g., [iface, action] or [iface, position</y>, action]).
        # The leaf level's chain is the original requirement's chain.
        parts: list[str] = []
        current = self
        while current is not None:
            parts.append(
                current._resolved_chain(current.inferred_from.chain, caller_fqun)
            )
            current = current.propagated_from
        return "::".join(parts)

    def _resolved_chain(self, chain: ast.ChainedName, caller_fqun: ast.Fqun) -> str:
        fqun = self.enclosing_action.typed_name.name_content.fqun
        if fqun.canonical == caller_fqun.canonical:
            return chain.source_chained_name
        return chain.canonical_chained_name(in_universe=fqun)

    def propagated_from_locations(self) -> list[ast.SourcePosition]:
        """Collect source locations from the propagated_from chain."""
        chain: list[ast.SourcePosition] = []
        current = self.propagated_from
        while current is not None:
            chain.append(current.inferred_from.position)
            current = current.propagated_from
        return chain


@dataclass(frozen=True)
class InterfacePositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""

    caused_by: ast.PositionReference


@dataclass(frozen=True)
class EmptyGuarantee(InterfacePositionGuarantee):
    """The position is guaranteed to be empty after the action completes."""


@dataclass(frozen=True)
class OccupiedByExistingGuarantee(InterfacePositionGuarantee):
    """The position contains the same DP that was passed into another interface position."""

    origin_position: ast.PositionReference


@dataclass(frozen=True)
class OccupiedByNewGuarantee(InterfacePositionGuarantee):
    """The position contains a new DP created by the action."""

    qualities: frozenset[str]


@dataclass(frozen=True)
class UnknownGuarantee(InterfacePositionGuarantee):
    """The position's state could not be determined due to an error."""


@dataclass(frozen=True)
class ActionContract:
    """The automatically inferred requirements and guarantees for an action."""

    requirements: dict[tuple[str, ...], InterfacePositionRequirement]
    guarantees: dict[tuple[str, ...], InterfacePositionGuarantee]
    # TODO: Support triggering on chained names?
    trigger_position_name: str


@dataclass(frozen=True, init=False)
class EmptyContract(ActionContract):
    """An action contract with no requirements, guarantees, or trigger."""

    def __init__(self):
        """Initialize with empty requirements, guarantees, and no trigger."""
        super().__init__(requirements={}, guarantees={}, trigger_position_name="")
