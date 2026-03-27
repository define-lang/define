"""Action contract types: automatically inferred requirements and guarantees."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
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
    inferred_from: ast.PositionReference


@dataclass(frozen=True)
class InterfacePositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""


@dataclass(frozen=True)
class EmptyGuarantee(InterfacePositionGuarantee):
    """The position is guaranteed to be empty after the action completes."""

    caused_by: ast.PositionReference | None = None


@dataclass(frozen=True)
class OccupiedByExistingGuarantee(InterfacePositionGuarantee):
    """The position contains the same DP that was passed into another interface position."""

    origin_position: ast.PositionReference
    caused_by: ast.PositionReference


@dataclass(frozen=True)
class OccupiedByNewGuarantee(InterfacePositionGuarantee):
    """The position contains a new DP created by the action."""

    qualities: frozenset[str]
    caused_by: ast.PositionReference


@dataclass(frozen=True)
class UnknownGuarantee(InterfacePositionGuarantee):
    """The position's state could not be determined due to an error."""


@dataclass(frozen=True)
class ActionContract:
    """The automatically inferred requirements and guarantees for an action."""

    requirements: dict[str, InterfacePositionRequirement]
    guarantees: dict[str, InterfacePositionGuarantee]
    # TODO: Support triggering on chained names?
    trigger_position_name: str


@dataclass(frozen=True, init=False)
class EmptyContract(ActionContract):
    """An action contract with no requirements, guarantees, or trigger."""

    def __init__(self):
        """Initialize with empty requirements, guarantees, and no trigger."""
        super().__init__(requirements={}, guarantees={}, trigger_position_name="")
