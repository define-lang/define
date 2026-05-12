"""Operations representing dimension point state transitions, and their executor."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph import dimension_point_tracker


@dataclass(frozen=True, slots=True)
class Operation:
    """Base type for dimension point state transition operations."""


@dataclass(frozen=True, slots=True)
class Create(Operation):
    """Place a freshly created dimension point at a position with the given qualities."""

    position: ast.PositionReference
    qualities: frozenset[str]


@dataclass(frozen=True, slots=True)
class AssumeOccupied(Create):
    """Place a dimension point that came from outside this body (caller-supplied or contracted)."""

    contracted_position_chain: ast.PositionReference


@dataclass(frozen=True, slots=True)
class Move(Operation):
    """Move the dimension point at source to target."""

    source: ast.PositionReference
    target: ast.PositionReference


@dataclass(frozen=True, slots=True)
class Destroy(Operation):
    """Remove the dimension point at a position."""

    position: ast.PositionReference


class DimensionPointOperationExecutor:
    """Runs operations against a DimensionPointTracker.

    For now, the execute methods are pure pass-through wrappers around
    the equivalent tracker methods. Subsequent refactor steps will move
    legality checks and diagnostic production into this class.
    """

    _tracker: dimension_point_tracker.DimensionPointTracker

    def __init__(self, tracker: dimension_point_tracker.DimensionPointTracker):
        """Store the tracker that operations will mutate."""
        self._tracker = tracker

    def execute_create(self, op: Create):
        """Place a freshly created dimension point on the tracker."""
        self._tracker.create(op.position, op.qualities)

    def execute_assume_occupied(self, op: AssumeOccupied):
        """Record a caller-supplied dimension point on the tracker."""
        self._tracker.create(
            op.position, op.qualities, from_caller=op.contracted_position_chain
        )

    def execute_move(self, op: Move):
        """Move a dimension point on the tracker from source to target."""
        self._tracker.move(op.source, op.target)

    def execute_destroy(self, op: Destroy):
        """Remove a dimension point from the tracker."""
        self._tracker.destroy(op.position)
