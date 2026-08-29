"""Tracks interface arrivals that must remain until their callee triggers."""

from __future__ import annotations

import collections
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

    from define.compiler import ast
    from define.compiler.validator.reference_graph import particle_tracker


class DeadInterfaceTracker:
    """Tracks whether interface arrivals remain until their callee triggers."""

    def __init__(self):
        """Initialize without any arrivals."""
        # Each callee key is the particle to which the action is assigned (or
        # None for an action implied by the current action) and the action's full
        # name. Each value maps an arrived particle to the exact action and
        # position references needed if that arrival is diagnosed.
        self._callee_interfaces: collections.defaultdict[
            tuple[particle_tracker.ParticleInfo | None, str],
            dict[
                particle_tracker.ParticleInfo,
                tuple[ast.GlobalTypedNameReference, ast.PositionReference],
            ],
        ] = collections.defaultdict(dict)
        # Each arrived particle maps back to its callee so a move or destruction
        # can find the arrival without scanning every callee. A particle can be
        # at only one position, and only the final action in that position's name
        # matters, so it can have only one pending callee.
        self._callee_by_interface_particle: dict[
            particle_tracker.ParticleInfo,
            tuple[particle_tracker.ParticleInfo | None, str],
        ] = {}
        # These action and position references describe arrivals whose particles
        # departed before the corresponding action triggered.
        self._dead_arrivals: list[
            tuple[ast.GlobalTypedNameReference, ast.PositionReference]
        ] = []

    def register_arrival(
        self,
        action: ast.GlobalTypedNameReference,
        position: ast.PositionReference,
        parent_particle: particle_tracker.ParticleInfo | None,
        particle: particle_tracker.ParticleInfo,
    ):
        """Track a particle arriving at an action interface position or child."""
        callee_key = (parent_particle, action.full_typed_name)
        self._callee_interfaces[callee_key][particle] = (action, position)
        self._callee_by_interface_particle[particle] = callee_key

    def mark_particle_departed(self, particle: particle_tracker.ParticleInfo):
        """Mark every interface arrival of a moved or destroyed particle dead."""
        if not self._callee_by_interface_particle:
            return
        callee_key = self._callee_by_interface_particle.pop(particle, None)
        if callee_key is None:
            return
        pending_arrivals = self._callee_interfaces[callee_key]
        self._dead_arrivals.append(pending_arrivals.pop(particle))
        if not pending_arrivals:
            del self._callee_interfaces[callee_key]

    def mark_action_triggered(
        self,
        action: ast.GlobalTypedNameReference,
        parent_particle: particle_tracker.ParticleInfo | None,
    ):
        """Satisfy pending interface arrivals for one callee on one particle."""
        callee_key = (parent_particle, action.full_typed_name)
        pending_arrivals = self._callee_interfaces.pop(callee_key, None)
        if pending_arrivals is None:
            return
        for particle in pending_arrivals:
            del self._callee_by_interface_particle[particle]

    def dead_arrivals(
        self,
    ) -> Iterable[tuple[ast.GlobalTypedNameReference, ast.PositionReference]]:
        """Return arrivals not satisfied by a trigger while their particles remained."""
        yield from self._dead_arrivals
        for pending_arrivals in self._callee_interfaces.values():
            yield from pending_arrivals.values()
