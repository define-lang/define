"""Tracks action-interface state that cannot be derived from final occupancy."""

from __future__ import annotations

import collections
import typing

import msgspec

from define.compiler import ast
from define.compiler.validator.reference_graph import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

# A quality on a particle, where None is the current action's parent particle.
type QualityOnParticle = tuple[particle_info.ParticleInfo | None, str]
type _Callee = QualityOnParticle


def interface_parent_name_indexes(
    position: ast.ChainedNameTuple,
) -> tuple[list[int], list[int]]:
    """Return the name indexes of the callees and interface parent qualities in a chained name.

    Returns:
        Two lists of indexes into ``position``:

        - Callees: each action that is followed by another action.
        - Interface parent qualities: each child name of a particle that is an
          action or is followed by one.
    """
    callee_indexes: list[int] = []
    interface_parent_quality_indexes: list[int] = []
    last_action_index: int | None = None
    for name_index, name in enumerate(position):
        if ast.is_action_key(name):
            last_action_index = name_index
    if last_action_index is None:
        return callee_indexes, interface_parent_quality_indexes
    previous_action_index: int | None = None
    for name_index, name in enumerate(position[: last_action_index + 1]):
        # Only a child name of a particle can be implied by a callee. The other
        # names are interface positions, which follow an action, and the
        # action's local positions, which start a chain.
        is_particle_child_name = (
            ast.chain_starts_with_global(position)
            if name_index == 0
            else not ast.is_action_key(position[name_index - 1])
        )
        if is_particle_child_name:
            interface_parent_quality_indexes.append(name_index)
        if not ast.is_action_key(name):
            continue
        if previous_action_index is not None:
            callee_indexes.append(previous_action_index)
        previous_action_index = name_index
    return callee_indexes, interface_parent_quality_indexes


class _PendingArrival(msgspec.Struct):
    """An explicit interface arrival awaiting its callee's trigger."""

    callee: _Callee
    position: ast.PositionReference


class _OccupiedInterfaceChildPosition(msgspec.Struct):
    """An occupied interface child position and the triggers that are invalid while it stays occupied.

    While the position is occupied, triggering one of ``callees``, or any
    callee that transitively implies one of ``interface_parent_qualities`` on
    the same particle, is a violation.
    """

    position: ast.ChainedNameTuple
    location: ast.SourceLocation
    callees: list[_Callee]
    interface_parent_qualities: list[QualityOnParticle]


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
        self._particles_by_interface_parent_quality: collections.defaultdict[
            QualityOnParticle, set[particle_info.ParticleInfo]
        ] = collections.defaultdict(set)

    def register(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
        interface_parent_qualities: list[QualityOnParticle],
    ):
        """Register an occupied interface child position for a new particle."""
        self._set(particle, position, location, callees, interface_parent_qualities)

    def replace(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
        interface_parent_qualities: list[QualityOnParticle],
    ):
        """Replace an existing particle's occupied interface child position."""
        occupied_position = self._by_particle.pop(particle, None)
        if occupied_position is not None:
            self._remove(particle, occupied_position)
        if not callees and not interface_parent_qualities:
            return
        self._set(particle, position, location, callees, interface_parent_qualities)

    def mark_particle_destroyed(self, particle: particle_info.ParticleInfo):
        """Discard an occupied position after its particle is destroyed."""
        occupied_position = self._by_particle.pop(particle, None)
        if occupied_position is not None:
            self._remove(particle, occupied_position)

    def pop_occupied_interface_child_positions(
        self,
        action_name: str,
        implied_quality_names: frozenset[str],
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
        """Remove and return occupied interface child positions for one callee."""
        particles: set[particle_info.ParticleInfo] = set()
        callee_particles = self._particles_by_callee.get((parent_particle, action_name))
        if callee_particles is not None:
            particles.update(callee_particles)
        if self._particles_by_interface_parent_quality:
            for quality_name in implied_quality_names:
                quality_particles = self._particles_by_interface_parent_quality.get(
                    (parent_particle, quality_name)
                )
                if quality_particles is not None:
                    particles.update(quality_particles)
        occupied_positions: list[tuple[ast.ChainedNameTuple, ast.SourceLocation]] = []
        for particle in particles:
            occupied_position = self._by_particle.pop(particle)
            occupied_positions.append(
                (occupied_position.position, occupied_position.location)
            )
            self._remove(particle, occupied_position)
        # This sort keeps multiple diagnostics on the same line/column in deterministic
        # order, and only fires in the error path.
        occupied_positions.sort(key=lambda occupied_position: occupied_position[0])
        return occupied_positions

    def _remove(
        self,
        particle: particle_info.ParticleInfo,
        occupied_position: _OccupiedInterfaceChildPosition,
    ):
        self._remove_from(
            self._particles_by_callee, particle, occupied_position.callees
        )
        self._remove_from(
            self._particles_by_interface_parent_quality,
            particle,
            occupied_position.interface_parent_qualities,
        )

    @staticmethod
    def _remove_from(
        particles_by_parent_name: collections.defaultdict[
            QualityOnParticle, set[particle_info.ParticleInfo]
        ],
        particle: particle_info.ParticleInfo,
        parent_names: list[QualityOnParticle],
    ):
        for parent_name in parent_names:
            occupied_particles = particles_by_parent_name[parent_name]
            occupied_particles.remove(particle)
            if not occupied_particles:
                del particles_by_parent_name[parent_name]

    def _set(
        self,
        particle: particle_info.ParticleInfo,
        position: ast.ChainedNameTuple,
        location: ast.SourceLocation,
        callees: list[_Callee],
        interface_parent_qualities: list[QualityOnParticle],
    ):
        self._by_particle[particle] = _OccupiedInterfaceChildPosition(
            position, location, callees, interface_parent_qualities
        )
        for callee in callees:
            self._particles_by_callee[callee].add(particle)
        for interface_parent_quality in interface_parent_qualities:
            self._particles_by_interface_parent_quality[interface_parent_quality].add(
                particle
            )


class ParticleLookup(typing.Protocol):
    """Current particle state, as seen by the action being validated."""

    def occupant(self, key: ast.ChainedNameTuple) -> particle_info.ParticleInfo:
        """Return the particle at this position, raising KeyError if it is empty."""
        ...

    def has_error_in_chain(self, key: ast.ChainedNameTuple) -> bool:
        """Return whether this position or any parent position has error occupancy state."""
        ...


@typing.final
class DeadInterfaceTracker:
    """Tracks the particle events that determine dead action-interface diagnostics."""

    def __init__(self, particles: ParticleLookup):
        """Initialize without interface arrivals or occupied interface child positions."""
        self._particles = particles
        self._arrivals = InterfaceArrivalTracker()
        self._occupied_child_positions = OccupiedInterfaceChildPositionTracker()

    def register_occupied_interface_child_position(
        self,
        position: ast.ChainedNameTuple,
        particle: particle_info.ParticleInfo,
        location: ast.SourceLocation,
    ):
        """Record a new particle's occupied interface child position, if it has one."""
        callees, interface_parent_qualities = self._interface_parent_names_on_particles(
            position
        )
        if not callees and not interface_parent_qualities:
            return
        self._occupied_child_positions.register(
            particle, position, location, callees, interface_parent_qualities
        )

    def replace_occupied_interface_child_position(
        self,
        position: ast.ChainedNameTuple,
        particle: particle_info.ParticleInfo,
        location: ast.SourceLocation,
    ):
        """Replace an existing particle's occupied interface child position."""
        callees, interface_parent_qualities = self._interface_parent_names_on_particles(
            position
        )
        self._occupied_child_positions.replace(
            particle, position, location, callees, interface_parent_qualities
        )

    def register_explicit_action_interface_arrival(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
    ):
        """Record a body Create or Move whose target names an action interface."""
        action_chain = position.get_chain_to_last_action()
        if action_chain is None:
            return
        parent_position = action_chain.parent_position()
        # The caller has already resolved the target position, which also
        # resolves each of its parent positions.
        parent_particle = (
            self._particles.occupant(parent_position.canonical_chained_name_tuple)
            if parent_position is not None
            else None
        )
        self._arrivals.register(
            action_chain.get_last_action().full_typed_name,
            position,
            parent_particle,
            particle,
        )

    def mark_particle_departed(self, particle: particle_info.ParticleInfo):
        """Record that a particle left its position."""
        self._arrivals.mark_particle_departed(particle)

    def mark_particle_destroyed(self, particle: particle_info.ParticleInfo):
        """Record that a particle no longer exists."""
        self._arrivals.mark_particle_departed(particle)
        self._occupied_child_positions.mark_particle_destroyed(particle)

    def mark_action_triggered(
        self,
        action: ast.GlobalTypedNameReference,
        implied_quality_names: frozenset[str],
        parent_particle: particle_info.ParticleInfo | None,
    ) -> list[tuple[ast.ChainedNameTuple, ast.SourceLocation]]:
        """Record an Action Execution and return the occupied interface child positions it violates."""
        violations: list[tuple[ast.ChainedNameTuple, ast.SourceLocation]] = []
        occupied_positions = (
            self._occupied_child_positions.pop_occupied_interface_child_positions(
                action.full_typed_name, implied_quality_names, parent_particle
            )
        )
        for position, location in occupied_positions:
            if self._particles.has_error_in_chain(position):
                continue
            violations.append((position, location))
        self._arrivals.mark_action_triggered(action.full_typed_name, parent_particle)
        return violations

    def dead_arrivals(self) -> Iterator[ast.PositionReference]:
        """Yield explicit arrivals not satisfied by their callees' triggers."""
        return self._arrivals.dead_arrivals()

    def _interface_parent_names_on_particles(
        self, position: ast.ChainedNameTuple
    ) -> tuple[list[QualityOnParticle], list[QualityOnParticle]]:
        """Pair each callee and interface parent quality in this position's chained name with the particle it is on."""
        callee_indexes, interface_parent_quality_indexes = (
            interface_parent_name_indexes(position)
        )
        callees: list[QualityOnParticle] = []
        for name_index in callee_indexes:
            callees.append(self._quality_on_particle(position, name_index))
        interface_parent_qualities: list[QualityOnParticle] = []
        for name_index in interface_parent_quality_indexes:
            interface_parent_qualities.append(
                self._quality_on_particle(position, name_index)
            )
        return callees, interface_parent_qualities

    def _quality_on_particle(
        self, position: ast.ChainedNameTuple, name_index: int
    ) -> QualityOnParticle:
        """Pair the name at ``name_index`` with its particle, or None for this action's parent particle."""
        particle = (
            None if name_index == 0 else self._particles.occupant(position[:name_index])
        )
        return particle, position[name_index]
