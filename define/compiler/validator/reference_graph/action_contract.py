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
class InterfacePositionRequirement:
    """An automatically inferred requirement on an action interface position."""

    position: ast.LocalPositionDefinition
    required_state: PositionOccupancyState
    inferred_from: ast.SourcePosition


@dataclass(frozen=True)
class InterfacePositionGuarantee:
    """An automatically inferred guarantee about an interface position after action completion."""

    position: ast.LocalPositionDefinition


@dataclass(frozen=True)
class EmptyGuarantee(InterfacePositionGuarantee):
    """The position is guaranteed to be empty after the action completes."""

    caused_by: ast.SourcePosition | None = None


@dataclass(frozen=True)
class OccupiedByExistingGuarantee(InterfacePositionGuarantee):
    """The position contains the same DP that was passed into another interface position."""

    origin_position: ast.LocalPositionDefinition
    caused_by: ast.SourcePosition


@dataclass(frozen=True)
class OccupiedByNewGuarantee(InterfacePositionGuarantee):
    """The position contains a new DP created by the action."""

    qualities: frozenset[str]
    caused_by: ast.SourcePosition


@dataclass(frozen=True)
class UnknownGuarantee(InterfacePositionGuarantee):
    """The position's state could not be determined due to an error."""


@dataclass(frozen=True)
class ActionAndInterfacePosition:
    """An action and one of its interface positions, resolved from a chained name."""

    action_name: str
    position_name: str

    @staticmethod
    def from_position_reference(
        ref: ast.PositionReference,
        enclosing_fqun: ast.Fqun,
    ) -> ActionAndInterfacePosition | None:
        """Resolve a position reference to an action and interface position, if it contains one at the end.

        Returns None if the chain does not end with an action's interface position.
        """
        elements = ref.chain.typed_names
        if len(elements) < 2:
            return None
        second_to_last = elements[-2]
        last = elements[-1]
        if second_to_last.name_type != ast.NameType.ACTION:
            return None
        if not isinstance(last, ast.LocalTypedNameReference):
            return None
        return ActionAndInterfacePosition(
            action_name=second_to_last.full_typed_name(in_universe=enclosing_fqun),
            position_name=last.name_content.name,
        )


@dataclass(frozen=True)
class ActionContract:
    """The automatically inferred requirements and guarantees for an action."""

    requirements: dict[str, InterfacePositionRequirement]
    guarantees: dict[str, InterfacePositionGuarantee]
    trigger_position_name: str


@dataclass(frozen=True, init=False)
class EmptyContract(ActionContract):
    """An action contract with no requirements, guarantees, or trigger."""

    def __init__(self):
        """Initialize with empty requirements, guarantees, and no trigger."""
        super().__init__(requirements={}, guarantees={}, trigger_position_name="")
