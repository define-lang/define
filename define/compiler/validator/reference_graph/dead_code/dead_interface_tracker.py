"""Tracks action-interface state that cannot be derived from final occupancy."""

from __future__ import annotations

import collections
import typing
from dataclasses import dataclass

from define.compiler.validator.reference_graph import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler import ast

type _Callee = tuple[particle_info.ParticleInfo | None, str]


@dataclass(slots=True)
class _PendingArrival:
    """An explicit interface arrival awaiting its callee's trigger."""

    callee: _Callee
    position: ast.PositionReference


@dataclass(slots=True)
class _OccupiedInterfaceChildPosition:
    """An occupied interface child position and the callees it prevents from triggering."""

    position: ast.ChainedNameTuple
    location: ast.SourceLocation
    callees: list[_Callee]


class InterfaceArrivalTracker:
    """Tracks interface arrivals awaiting their callees' triggers."""

    def __init__(self):
        """Initialize without interface arrivals."""
        self._by_particle: dict[particle_info.ParticleInfo, _PendingArrival] = {}
        self._particles_by_callee: collections.defaultdict[
            _Callee, set[particle_info.ParticleInfo]
        ] = collections.defaultdict(set)
        self._dead_arrivals: list[ast.PositionReference] = []

    def register(
        self,
        action_name: str,
        position: ast.PositionReference,
        parent_particle: particle_info.ParticleInfo | None,
        particle: particle_info.ParticleInfo,
    ):
        """Record an explicit arrival at an action interface position or child."""
        callee = (parent_particle, action_name)
        self._by_particle[particle] = _PendingArrival(callee, position)
        self._particles_by_callee[callee].add(particle)

    def mark_particle_departed(self, particle: particle_info.ParticleInfo):
        """Mark an arrival dead after its particle moves or is destroyed."""
        pending_arrival = self._by_particle.pop(particle, None)
        if pending_arrival is None:
            return
        pending_particles = self._particles_by_callee[pending_arrival.callee]
        pending_particles.remove(particle)
        if not pending_particles:
            del self._particles_by_callee[pending_arrival.callee]
        self._dead_arrivals.append(pending_arrival.position)

    def mark_action_triggered(
        self,
        action_name: str,
        parent_particle: particle_info.ParticleInfo | None,
    ):
        """Satisfy pending explicit arrivals for one triggered action."""
        callee = (parent_particle, action_name)
        pending_particles = self._particles_by_callee.pop(callee, None)
        if pending_particles is None:
            return
        for particle in pending_particles:
            del self._by_particle[particle]

    def dead_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit arrivals not satisfied by their callees' triggers."""
        yield from self._dead_arrivals
        for pending_arrival in self._by_particle.values():
            yield pending_arrival.position


class OccupiedInterfaceChildPositionTracker:
    """Tracks occupied interface child positions that prevent action triggering."""

    def __init__(self):
        """Initialize without occupied interface child positions."""
        self._by_particle: dict[
            particle_info.ParticleInfo, _OccupiedInterfaceChildPosition
        ] = {}
        self._particles_by_callee: collections.defaultdict[
            _Callee, set[particle_info.ParticleInfo]
        ] = collections.defaultdict(set)

    def register(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
    ):
        """Register an occupied interface child position for a new particle."""
        self._set(particle, position, location, callees)

    def replace(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
    ):
        """Replace an existing particle's occupied interface child position."""
        occupied_position = self._by_particle.pop(particle, None)
        if occupied_position is not None:
            self._remove(particle, occupied_position)
        if not callees:
            return
        self._set(particle, position, location, callees)

    def mark_particle_destroyed(self, particle: particle_info.ParticleInfo):
        """Discard an occupied position after its particle is destroyed."""
        occupied_position = self._by_particle.pop(particle, None)
        if occupied_position is not None:
            self._remove(particle, occupied_position)

    def pop_occupied_interface_child_positions(
        self,
        action_name: str,
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
        """Remove and return occupied interface child positions for one callee."""
        callee = (parent_particle, action_name)
        occupied_positions: list[tuple[ast.ChainedNameTuple, ast.SourceLocation]] = []
        particles = self._particles_by_callee.pop(callee, None)
        if particles is None:
            return occupied_positions
        for particle in particles:
            occupied_position = self._by_particle.pop(particle)
            occupied_positions.append(
                (occupied_position.position, occupied_position.location)
            )
            self._remove(particle, occupied_position, removed_callee=callee)
        # This sort keeps multiple diagnostics on the same line/column in deterministic
        # order, and only fires in the error path.
        occupied_positions.sort(key=lambda occupied_position: occupied_position[0])
        return occupied_positions

    def _remove(
        self,
        particle: particle_info.ParticleInfo,
        occupied_position: _OccupiedInterfaceChildPosition,
        *,
        removed_callee: _Callee | None = None,
    ):
        for callee in occupied_position.callees:
            if callee == removed_callee:
                continue
            occupied_particles = self._particles_by_callee[callee]
            occupied_particles.remove(particle)
            if not occupied_particles:
                del self._particles_by_callee[callee]

    def _set(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
    ):
        self._by_particle[particle] = _OccupiedInterfaceChildPosition(
            position, location, callees
        )
        for callee in callees:
            self._particles_by_callee[callee].add(particle)
