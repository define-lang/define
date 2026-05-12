"""Operations representing dimension point state transitions, and their executor."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import diagnostics

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

    Owns the post-parents-occupied legality rules for create/move/destroy
    and produces diagnostics on illegal state transitions.
    """

    _tracker: dimension_point_tracker.DimensionPointTracker

    def __init__(self, tracker: dimension_point_tracker.DimensionPointTracker):
        """Store the tracker that operations will mutate."""
        self._tracker = tracker

    def execute_create(self, op: Create) -> diagnostics.Diagnostic | None:
        """Place a freshly created dimension point on the tracker."""
        if self._tracker.is_occupied(op.position):
            return diagnostics.CreateInOccupiedPositionDiagnostic(
                location=op.position.location,
                position_name=op.position.source_chained_name,
                populated_at=self._tracker.get_occupant(
                    op.position
                ).last_position.location,
            )
        self._tracker.create(op.position, op.qualities)
        return None

    def execute_assume_occupied(self, op: AssumeOccupied):
        """Record a caller-supplied dimension point on the tracker."""
        self._tracker.create(
            op.position, op.qualities, from_caller=op.contracted_position_chain
        )

    def execute_move(self, op: Move) -> list[diagnostics.Diagnostic]:
        """Move a dimension point on the tracker from source to target."""
        from_occupied = self._tracker.is_occupied(op.source)
        to_empty = not self._tracker.is_occupied(op.target)
        diags: list[diagnostics.Diagnostic] = []
        if not from_occupied:
            from_action = op.source.get_last_action()
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(op.source)
                diags.append(
                    diagnostics.MoveFromEmptyInterfacePositionDiagnostic(
                        location=op.source.location,
                        position_name=op.source.source_chained_name,
                        inferred_at=emptied_by.location if emptied_by else None,
                    )
                )
            else:
                diags.append(
                    diagnostics.MoveFromEmptyPositionDiagnostic(
                        location=op.source.location,
                        position_name=op.source.source_chained_name,
                    )
                )
        if not to_empty:
            occupant = self._tracker.get_occupant(op.target)
            diags.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    location=op.target.location,
                    position_name=op.target.source_chained_name,
                    occupied_at=occupant.last_position.location,
                )
            )
        if diags:
            return diags
        self._tracker.move(op.source, op.target)
        return []

    def execute_destroy(self, op: Destroy) -> diagnostics.Diagnostic | None:
        """Remove a dimension point from the tracker."""
        if not self._tracker.is_occupied(op.position):
            from_action = op.position.get_last_action()
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(op.position)
                return diagnostics.DestroyInEmptyInterfacePositionDiagnostic(
                    location=op.position.location,
                    position_name=op.position.source_chained_name,
                    inferred_at=emptied_by.location if emptied_by else None,
                )
            return diagnostics.DestroyInEmptyPositionDiagnostic(
                location=op.position.location,
                position_name=op.position.source_chained_name,
            )
        self._tracker.destroy(op.position)
        return None
