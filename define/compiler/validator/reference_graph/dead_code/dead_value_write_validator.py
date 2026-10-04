"""Validate that written values are used (DLP 42)."""

from __future__ import annotations

import typing

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from define.compiler import ast, chained_name
    from define.compiler.validator.reference_graph import action_contract
    from define.compiler.validator.reference_graph.particles import (
        particle_info,
        particle_tracker,
    )


class DeadValueWriteValidator:
    """Track each particle's latest value write until something uses it, and diagnose the unused ones."""

    _tracker: particle_tracker.ParticleTracker
    _unused_writes: dict[particle_info.ParticleInfo, ast.PositionReference]

    def __init__(self, tracker: particle_tracker.ParticleTracker):
        """Initialize with the action's particle state."""
        self._tracker = tracker
        self._unused_writes = {}

    def record_write(
        self, position: ast.PositionReference
    ) -> list[diagnostics.DeadValueWriteDiagnostic]:
        """Record a value write, and diagnose the particle's previous write if nothing used it."""
        particle = self._tracker.get_occupant(position)
        previous_write = self._unused_writes.get(particle)
        self._unused_writes[particle] = position
        if previous_write is None:
            return []
        return [_dead_value_write(previous_write)]

    def mark_used(self, position: ast.PositionReference):
        """Mark the value of the particle at this position as used."""
        particle = self._tracker.get_occupant_or_none(position)
        if particle is not None:
            self.mark_particle_used(particle)

    def mark_particle_used(self, particle: particle_info.ParticleInfo):
        """Mark the particle's latest value write as used."""
        _ = self._unused_writes.pop(particle, None)

    def mark_required_values_used(
        self,
        value_requirements: list[action_contract.ValueRequirementInCaller],
    ):
        """Mark the values a triggered action requires as used."""
        for requirement in value_requirements:
            self.mark_used(requirement.caller_position)

    def validate(
        self,
        guarantees: dict[
            chained_name.PositionReferenceTuple,
            action_contract.PositionGuarantee,
        ],
    ) -> list[diagnostics.DeadValueWriteDiagnostic]:
        """Diagnose value writes that nothing used, unless this action guarantees them."""
        if not self._unused_writes:
            return []
        for key in guarantees:
            occupant = self._tracker.occupant_or_none_by_key(key)
            if occupant is not None:
                self.mark_particle_used(occupant)
        return [
            _dead_value_write(position) for position in self._unused_writes.values()
        ]


def _dead_value_write(
    position: ast.PositionReference,
) -> diagnostics.DeadValueWriteDiagnostic:
    return diagnostics.DeadValueWriteDiagnostic(
        location=position.location,
        position_name=position.source_chained_name,
    )
