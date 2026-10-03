"""Tracks explicit action-interface arrivals awaiting their callees' triggers."""

from __future__ import annotations

import collections
import typing

import msgspec

from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast

# An action on a particle, where None is the current action's parent particle.
type _Callee = tuple[particle_info.ParticleInfo | None, str]


class _PendingInterfaceArrival(msgspec.Struct):
    """An explicit interface arrival awaiting its callee's trigger."""

    callee: _Callee
    position: ast.PositionReference


class InterfaceArrivalTracker:
    """Tracks interface arrivals awaiting their callees' triggers."""

    def __init__(self):
        """Initialize without interface arrivals."""
        self._by_particle: dict[
            particle_info.ParticleInfo, _PendingInterfaceArrival
        ] = {}
        # The inner dictionaries are ordered sets, which keep diagnostics in
        # the order of the interface arrivals.
        self._particles_by_callee: collections.defaultdict[
            _Callee, dict[particle_info.ParticleInfo, None]
        ] = collections.defaultdict(dict)
        self._dead_interface_arrivals: list[ast.PositionReference] = []

    def register(
        self,
        position: ast.PositionReference,
        parent_particle: particle_info.ParticleInfo | None,
        particle: particle_info.ParticleInfo,
    ):
        """Record an explicit interface arrival at an action interface position or child, whose action runs on ``parent_particle``."""
        # Only a position below an action is an interface arrival.
        action = typing.cast("ast.GlobalTypedNameReference", position.get_last_action())
        callee = (parent_particle, action.full_typed_name)
        self._by_particle[particle] = _PendingInterfaceArrival(callee, position)
        self._particles_by_callee[callee][particle] = None

    def mark_particle_departed(self, particle: particle_info.ParticleInfo):
        """Mark an interface arrival dead because its particle left the position it arrived in before its callee triggered."""
        pending_interface_arrival = self._by_particle.get(particle)
        if pending_interface_arrival is None:
            return
        self._remove(particle, pending_interface_arrival)
        self._dead_interface_arrivals.append(pending_interface_arrival.position)

    def mark_particle_passed_to_callee(self, particle: particle_info.ParticleInfo):
        """Satisfy the interface arrival of a particle that is in its position when its callee triggers."""
        self._remove(particle, self._by_particle[particle])

    def pending_interface_arrivals(
        self,
        action: ast.ActionReference,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[particle_info.ParticleInfo, ast.PositionReference]]:
        """Return each particle whose interface arrival awaits the trigger of ``action``, which runs on ``parent_particle``, with where it arrived."""
        interface_arrivals: list[
            tuple[particle_info.ParticleInfo, ast.PositionReference]
        ] = []
        for particle in self._particles_by_callee.get(
            (parent_particle, action.get_last_action().full_typed_name), ()
        ):
            interface_arrivals.append((particle, self._by_particle[particle].position))
        return interface_arrivals

    def dead_interface_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit interface arrivals not satisfied by their callees' triggers."""
        yield from self._dead_interface_arrivals
        for pending_interface_arrival in self._by_particle.values():
            yield pending_interface_arrival.position

    def _remove(
        self,
        particle: particle_info.ParticleInfo,
        pending_interface_arrival: _PendingInterfaceArrival,
    ):
        del self._by_particle[particle]
        pending_particles = self._particles_by_callee[pending_interface_arrival.callee]
        del pending_particles[particle]
        if not pending_particles:
            del self._particles_by_callee[pending_interface_arrival.callee]
