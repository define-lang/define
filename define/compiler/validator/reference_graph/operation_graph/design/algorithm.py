"""Collection and Comparison for resolved, valid Define Particle Operations."""

from __future__ import annotations

import dataclasses
from typing import final

from . import graph

# These limits bound optional pruning; larger collections still receive full
# Comparison, so skipping a shortcut cannot change the graph.
MAX_PRUNING_CANDIDATES = 16
MAX_SETTER_SEARCH_CANDIDATES = 16
# Shared traversal avoids repeated searches in wide collections, but starts
# too much traversal work when used for small collections.
MAX_PAIRWISE_COMPARISON_CANDIDATES = 64


@dataclasses.dataclass(slots=True, frozen=True)
class Operation:
    """Resolved position and particle requirements of one Particle Operation."""

    occupied: tuple[int, ...] = ()
    fill: int | None = None
    empty: int | None = None
    quality_particles: tuple[int, ...] = ()
    defines: tuple[int, ...] = ()
    ordinary_occupants: tuple[int, ...] = ()
    moved: int | None = None
    vacated: int | None = None


def classify(operations: list[Operation]) -> set[int]:
    """Identify particles for which ordinary occupancy does not certify combination."""
    separate: set[int] = set()
    # Most particles may never Move; tracking later Moves avoids retaining
    # every destroyed identity solely to detect retained movement.
    moved_later: set[int] = set()
    for operation in reversed(operations):
        ordinary = operation.ordinary_occupants
        covered = set(ordinary) if len(ordinary) > 1 else ordinary
        for particle in operation.quality_particles:
            if particle not in covered:
                separate.add(particle)
        if operation.vacated is not None and operation.vacated in moved_later:
            separate.add(operation.vacated)
        if operation.moved is not None:
            moved_later.add(operation.moved)
    return separate


@dataclasses.dataclass(slots=True)
class _Position:
    setter: int
    readers: set[int] | None = None
    parent_create: int | None = None
    recent_use: int | None = None


def compare(calculated: graph.Graph, candidates: set[int]) -> list[int]:
    """Apply Comparison before adding the current operation's edges."""
    if len(candidates) < 2:
        return list(candidates)
    if len(candidates) == 2:
        first, second = candidates
        if calculated.heights[first] < calculated.heights[second]:
            first, second = second, first
        if calculated.reaches_indexed(first, second):
            return [first]
        return [first, second]
    if len(candidates) > MAX_PAIRWISE_COMPARISON_CANDIDATES:
        heights = [calculated.heights[candidate] for candidate in candidates]
        minimum_height = min(heights)
        if minimum_height == max(heights):
            return list(candidates)
        direct: set[int] = set()
        for candidate in candidates:
            for offset in range(
                calculated.offsets[candidate], calculated.offsets[candidate + 1]
            ):
                dependency = calculated.edges[offset]
                if dependency in candidates:
                    direct.add(dependency)
        if direct:
            candidates = candidates - direct
            if len(candidates) < 2:
                return list(candidates)
            minimum_height = min(
                calculated.heights[candidate] for candidate in candidates
            )
        minimum_occurrence = min(candidates)
        expanded = set(candidates)
        excluded: set[int] = set()
        pending = list(candidates)
        while pending:
            current = pending.pop()
            if (
                current <= minimum_occurrence
                or calculated.heights[current] <= minimum_height
            ):
                continue
            for offset in range(
                calculated.offsets[current], calculated.offsets[current + 1]
            ):
                dependency = calculated.edges[offset]
                if dependency in candidates:
                    excluded.add(dependency)
                    if len(excluded) == len(candidates) - 1:
                        return list(candidates - excluded)
                if (
                    calculated.heights[dependency] >= minimum_height
                    and dependency >= minimum_occurrence
                    and dependency not in expanded
                ):
                    expanded.add(dependency)
                    pending.append(dependency)
        return list(candidates - excluded)
    ordered = sorted(candidates, key=calculated.heights.__getitem__, reverse=True)
    if calculated.heights[ordered[0]] == calculated.heights[ordered[-1]]:
        return ordered
    kept: list[int] = []
    for candidate in ordered:
        if not any(calculated.reaches_indexed(later, candidate) for later in kept):
            kept.append(candidate)
    return kept


@final
class Calculator:
    """Calculate dependencies while following the specified serial state."""

    def __init__(
        self,
        separate_particles: set[int],
        cache_targets: int = 1024,
        cache_bytes: int = 64 * 1024**2,
    ):
        """Keep occupancy analysis separate from dependency reachability."""
        self.graph = graph.Graph(cache_targets, cache_bytes)
        self._positions: dict[int, _Position] = {}
        self._separate_particles = separate_particles
        self._vanishes: dict[int, int] = {}
        self._particle_uses: dict[int, set[int]] = {}
        self._last_moves: dict[int, int] = {}
        self._vacates: dict[int, int] = {}

    def retain(self, positions: dict[int, int]):
        """Preserve position information for shared destructor use."""
        for ordinary, retained in positions.items():
            state = self._positions[ordinary]
            readers = None if state.readers is None else state.readers.copy()
            self._positions[retained] = _Position(
                state.setter,
                readers,
                state.parent_create,
                state.recent_use,
            )

    def forget(self, positions: tuple[int, ...]):
        """Release records after source analysis proves they have no future uses."""
        for position in positions:
            del self._positions[position]

    def _collect(self, operation: Operation) -> set[int]:
        candidates = set(operation.quality_particles)
        covered_creates: set[int] = set()
        read_positions: list[_Position] = []
        required = operation.occupied
        if operation.fill is not None:
            required = (*required, operation.fill)
        for position in required:
            state = self._positions.get(position)
            if state is not None:
                candidates.add(state.setter)
                if state.readers is not None:
                    read_positions.append(state)
                if (
                    state.parent_create is not None
                    and state.setter != state.parent_create
                ):
                    covered_creates.add(state.parent_create)
        if operation.empty is not None:
            state = self._positions[operation.empty]
            if state.readers is None:
                candidates.add(state.setter)
            else:
                candidates.update(state.readers)
            if state.parent_create is not None and (
                state.readers is not None or state.setter != state.parent_create
            ):
                covered_creates.add(state.parent_create)
        candidates.difference_update(covered_creates)
        covered: list[int] = []
        for state in read_positions:
            if state.setter not in candidates:
                continue
            assert state.readers is not None  # noqa: S101 - Established when collected above.
            if len(candidates) <= MAX_SETTER_SEARCH_CANDIDATES:
                follows_fill = not candidates.isdisjoint(state.readers)
            else:
                follows_fill = state.recent_use in candidates
            if follows_fill:
                covered.append(state.setter)
        candidates.difference_update(covered)
        return candidates

    def _record(self, operation: Operation, occurrence: int, collected: set[int]):
        for position in operation.occupied:
            state = self._positions[position]
            if state.readers is None:
                state.readers = {occurrence}
            else:
                # Bounding this optional pruning keeps long references from
                # multiplying work by an arbitrarily large dependency count.
                if len(collected) <= MAX_PRUNING_CANDIDATES:
                    state.readers.difference_update(collected)
                state.readers.add(occurrence)
            state.recent_use = occurrence
        for position in (operation.fill, operation.empty):
            if position is None:
                continue
            state = self._positions.get(position)
            if state is None:
                self._positions[position] = _Position(occurrence)
            else:
                state.setter = occurrence
                state.readers = None
                state.recent_use = None
        for position in operation.defines:
            self._positions[position] = _Position(occurrence, parent_create=occurrence)

        # A whole-input certificate makes even per-use filtering unnecessary.
        if not self._separate_particles:
            if operation.vacated is not None:
                self._vanishes[operation.vacated] = occurrence
            return

        ordinary = operation.ordinary_occupants
        covered = set(ordinary) if len(ordinary) > 1 else ordinary
        for particle in operation.quality_particles:
            if particle not in self._separate_particles or particle in covered:
                continue
            uses = self._particle_uses.setdefault(particle, set())
            if len(collected) <= MAX_PRUNING_CANDIDATES:
                uses.difference_update(collected)
            uses.add(occurrence)
        if operation.vacated is not None:
            if operation.vacated in self._separate_particles:
                self._vacates[operation.vacated] = occurrence
            else:
                self._vanishes[operation.vacated] = occurrence
        if operation.moved is not None and operation.moved in self._separate_particles:
            self._last_moves[operation.moved] = occurrence

    def finish(self) -> dict[int, int]:
        """Finish the graph; no further operations may be added."""
        self._positions.clear()
        for particle, vacate in self._vacates.items():
            candidates = self._particle_uses.pop(particle, None)
            if candidates is None:
                candidates = {vacate}
            else:
                candidates.add(vacate)
            moved = self._last_moves.pop(particle, None)
            if moved is not None:
                candidates.add(moved)
            dependencies = compare(self.graph, candidates)
            self._vanishes[particle] = (
                vacate
                if dependencies == [vacate]
                else self.graph.append_terminal(dependencies)
            )
        self._particle_uses.clear()
        self._last_moves.clear()
        self._vacates.clear()
        return self._vanishes

    def add(self, operation: Operation) -> int:
        """Calculate and record one Create, Move, or Vacate."""
        candidates = self._collect(operation)
        dependencies = compare(self.graph, candidates)
        occurrence = self.graph.append(dependencies)
        self._record(operation, occurrence, candidates)
        return occurrence

    def simultaneous(self, operations: list[Operation]) -> list[int]:
        """Calculate Vacates selected by one simultaneous destruction."""
        return [self.add(operation) for operation in operations]
