"""Operations representing particle state transitions, and their executor."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.validator.reference_graph import particle_tracker


@dataclass(frozen=True, slots=True)
class Operation:
    """Base type for particle operations."""

    target: ast.PositionReference


@dataclass(frozen=True, slots=True)
class Create(Operation):
    """Create a new particle in a position, with the given qualities."""

    qualities: tuple[ast.GlobalTypedNameReference, ...]


@dataclass(frozen=True, slots=True)
class AssumeOccupied(Create):
    """Place a particle that comes from the caller."""

    contracted_position_chain: ast.PositionReference


@dataclass(frozen=True, slots=True)
class AssumeEmpty(Operation):
    """Mark a position as known-empty per a contract requirement."""


@dataclass(frozen=True, slots=True)
class Move(Operation):
    """Move the particle in source to target."""

    source: ast.PositionReference
    target_required_qualities: tuple[ast.GlobalTypedNameReference, ...]


@dataclass(frozen=True, slots=True)
class Destroy(Operation):
    """Destroy the particle in a position."""


def _name_set(typed_names: tuple[ast.GlobalTypedNameReference, ...]) -> frozenset[str]:
    return frozenset(name.full_typed_name for name in typed_names)


class ParticleOperationExecutor:
    """Creates, destroys, and moves particles, including enforcing the rules on doing so."""

    _tracker: particle_tracker.ParticleTracker

    def __init__(self, tracker: particle_tracker.ParticleTracker):
        """Create a new ParticleOperationExecutor."""
        self._tracker = tracker

    def execute_create(self, op: Create) -> list[diagnostics.Diagnostic]:
        """Execute the Create operation."""
        parent_diags = self._check_parents_occupied(op.target)
        if parent_diags:
            self._tracker.mark_error(op.target)
            return parent_diags
        if self._tracker.is_occupied(op.target):
            # Target is genuinely occupied — leave its known state intact so
            # later statements can still reason about the existing particle.
            return [
                diagnostics.CreateInOccupiedPositionDiagnostic(
                    location=op.target.location,
                    position_name=op.target.source_chained_name,
                    populated_at=self._tracker.get_occupant(
                        op.target
                    ).last_position.location,
                )
            ]
        self._tracker.create(op.target, op.qualities)
        return []

    def execute_assume_occupied(self, op: AssumeOccupied):
        """Execute the AssumeOccupied operation."""
        self._tracker.create(
            op.target,
            op.qualities,
            from_caller=op.contracted_position_chain,
        )

    def execute_assume_empty(self, op: AssumeEmpty):
        """Execute the AssumeEmpty operation."""
        self._tracker.mark_empty(op.target)

    def execute_move(self, op: Move) -> list[diagnostics.Diagnostic]:
        """Execute the Move operation."""
        parent_diags = self._check_parents_occupied(
            op.source
        ) + self._check_parents_occupied(op.target)
        if parent_diags:
            self._tracker.mark_error(op.source)
            self._tracker.mark_error(op.target)
            return parent_diags
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
            self._tracker.mark_error(op.source)
            self._tracker.mark_error(op.target)
            return diags
        have = _name_set(self._tracker.get_occupant(op.source).qualities)
        missing = [
            name.full_typed_name
            for name in op.target_required_qualities
            if name.full_typed_name not in have
        ]
        if missing:
            self._tracker.mark_error(op.source)
            self._tracker.mark_error(op.target)
            return [
                diagnostics.MoveViolatesConstraintsDiagnostic(
                    location=op.target.location,
                    source_position=op.source.source_chained_name,
                    target_position=op.target.source_chained_name,
                    missing_qualities=missing,
                )
            ]
        self._tracker.move(op.source, op.target)
        return []

    def execute_destroy(
        self, op: Destroy, before_destroy: Callable[[], None] = lambda: None
    ) -> list[diagnostics.Diagnostic]:
        """Execute the Destroy operation.

        ``before_destroy`` runs only on the success path, immediately before the
        particle is removed. Destructors must fire while the particle
        still exists, so the caller passes their firing in here.
        """
        parent_diags = self._check_parents_occupied(op.target)
        if parent_diags:
            self._tracker.mark_error(op.target)
            return parent_diags
        if not self._tracker.is_occupied(op.target):
            self._tracker.mark_error(op.target)
            from_action = op.target.get_last_action()
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(op.target)
                return [
                    diagnostics.DestroyInEmptyInterfacePositionDiagnostic(
                        location=op.target.location,
                        position_name=op.target.source_chained_name,
                        inferred_at=emptied_by.location if emptied_by else None,
                    )
                ]
            return [
                diagnostics.DestroyInEmptyPositionDiagnostic(
                    location=op.target.location,
                    position_name=op.target.source_chained_name,
                )
            ]
        before_destroy()
        self._tracker.destroy(op.target)
        return []

    def _check_parents_occupied(
        self, target: ast.PositionReference
    ) -> list[diagnostics.Diagnostic]:
        """Walk parent positions leaf-to-root, emitting one diagnostic per empty parent."""
        diags: list[diagnostics.Diagnostic] = []
        current = target.parent_position()
        while current is not None:
            if self._tracker.is_occupied(current):
                break
            diags.append(
                diagnostics.ParentPositionNotOccupiedDiagnostic(
                    location=target.location,
                    position_name=target.source_chained_name,
                    parent_position_name=current.source_chained_name,
                )
            )
            current = current.parent_position()
        return diags
