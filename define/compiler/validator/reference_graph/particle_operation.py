"""Operations representing particle state transitions, and their executor."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.validator.reference_graph import (
        operation_graph_model,
        particle_tracker,
        quality_assignment,
    )


@dataclass(frozen=True, slots=True)
class Operation:
    """Base type for particle operations."""

    target: ast.PositionReference


@dataclass(frozen=True, slots=True)
class Create(Operation):
    """Create a new particle in a position, with the given qualities."""

    qualities: quality_assignment.QualityAssignments


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


class ParticleOperationExecutor:
    """Creates, destroys, and moves particles, including enforcing the rules on doing so."""

    _tracker: particle_tracker.ParticleTracker
    _enclosing_fqun: ast.Fqun

    def __init__(
        self, tracker: particle_tracker.ParticleTracker, enclosing_fqun: ast.Fqun
    ):
        """Create a new ParticleOperationExecutor."""
        self._tracker = tracker
        self._enclosing_fqun = enclosing_fqun

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
            is_action_interface_position = from_action is not None
            emptied_by = (
                self._tracker.get_emptied_by(op.source)
                if is_action_interface_position
                else None
            )
            diags.append(
                diagnostics.MoveFromEmptyPositionDiagnostic(
                    location=op.source.location,
                    position_name=op.source.source_chained_name,
                    is_action_interface_position=is_action_interface_position,
                    inferred_at=emptied_by.location if emptied_by else None,
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
        have = self._tracker.get_occupant(op.source).qualities
        missing = [
            name.source_form_in_universe(self._enclosing_fqun)
            for name in op.target_required_qualities
            if not have.has_quality(name)
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

    def execute_destroy[BeforeDestroyResultT](
        self,
        op: Destroy,
        before_destroy: Callable[[], BeforeDestroyResultT],
        *,
        destruction_fact: operation_graph_model.DestructionFact,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        BeforeDestroyResultT | None,
    ]:
        """Execute the Destroy operation.

        ``before_destroy`` runs only on the success path, immediately before the
        particle is removed. Destructors must fire while the particle
        still exists, so the caller passes their firing in here.
        """
        # TODO: Revisit the executor's responsibility for Particle Operations.
        # The validator expands and executes destruction-cascade children, while
        # this method validates the statement and executes only its final explicit
        # destruction. That ownership split forces the validator to exclude the
        # last cascade target from ``before_destroy``.
        parent_diags = self._check_parents_occupied(op.target)
        if parent_diags:
            self._tracker.mark_error(op.target)
            return parent_diags, None
        if not self._tracker.is_occupied(op.target):
            self._tracker.mark_error(op.target)
            from_action = op.target.get_last_action()
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(op.target)
                return (
                    [
                        diagnostics.DestroyInEmptyInterfacePositionDiagnostic(
                            location=op.target.location,
                            position_name=op.target.source_chained_name,
                            inferred_at=emptied_by.location if emptied_by else None,
                        )
                    ],
                    None,
                )
            return (
                [
                    diagnostics.DestroyInEmptyPositionDiagnostic(
                        location=op.target.location,
                        position_name=op.target.source_chained_name,
                    )
                ],
                None,
            )
        before_destroy_result = before_destroy()
        self._tracker.destroy_explicit(op.target, destruction_fact)
        return [], before_destroy_result

    def _check_parents_occupied(
        self, target: ast.PositionReference
    ) -> list[diagnostics.Diagnostic]:
        """Report the first unoccupied parent position in chained-name order."""
        parent_position = self._tracker.first_unoccupied_parent(target)
        if parent_position is None:
            return []
        return [
            diagnostics.ParentPositionNotOccupiedDiagnostic(
                location=target.location,
                position_name=target.source_chained_name,
                parent_position_name=parent_position.source_chained_name,
            )
        ]
