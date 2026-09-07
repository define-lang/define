"""Collection and Comparison for resolved, valid Define Particle Operations."""

from __future__ import annotations

import dataclasses
from typing import final

from define.compiler.validator.reference_graph.operation_graph.design import graph

# These bound optional work without skipping useful shortcuts on longer
# references. Measurement and crossover trade-offs are in the archived
# thresholds.md linked from README.md.
MAX_PRUNING_CANDIDATES = 16
MAX_SUPPLIER_SEARCH_CANDIDATES = 16
# Shared traversal avoids repeated searches in wide collections, but starts
# too much traversal work when used for small collections.
MAX_PAIRWISE_COMPARISON_CANDIDATES = 64


@dataclasses.dataclass(slots=True, frozen=True)
class Operation:
    """Requirements of one operation, with repeated position accesses combined."""

    occupied: tuple[int, ...] = ()
    fill: int | None = None
    empty: int | None = None
    creators: tuple[int, ...] = ()
    defines: tuple[int, ...] = ()


@dataclasses.dataclass(slots=True)
class _Position:
    supplier: int
    uses: set[int] | None = None
    creator: int | None = None
    recent_use: int | None = None


def compare(calculated: graph.Graph, candidates: set[int]) -> list[int]:
    """Apply Comparison before adding the current operation's edges."""
    if len(candidates) < 2:
        return list(candidates)
    if len(candidates) == 2:
        first, second = candidates
        if calculated.heights[first] < calculated.heights[second]:
            first, second = second, first
        if calculated.reaches(first, second):
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
        if not any(calculated.reaches(later, candidate) for later in kept):
            kept.append(candidate)
    return kept


@final
class Calculator:
    """Calculate dependencies while following the specified serial state."""

    def __init__(self, cache_targets: int = 1024, cache_bytes: int = 64 * 1024**2):
        """Keep occupancy analysis separate from dependency reachability."""
        self.graph = graph.Graph(cache_targets, cache_bytes)
        self._positions: dict[int, _Position] = {}

    def retain(self, positions: dict[int, int]):
        """Preserve selected records for shared destructor use before vacancy."""
        for ordinary, retained in positions.items():
            state = self._positions[ordinary]
            uses = None if state.uses is None else state.uses.copy()
            self._positions[retained] = _Position(
                state.supplier,
                uses,
                state.creator,
                state.recent_use,
            )

    def forget(self, positions: tuple[int, ...]):
        """Release records after source analysis proves they have no future uses."""
        for position in positions:
            del self._positions[position]

    def _collect(self, operation: Operation) -> set[int]:
        candidates = set(operation.creators)
        covered_creators: set[int] = set()
        supplied_by_uses: list[_Position] = []
        required = operation.occupied
        if operation.fill is not None:
            required = (*required, operation.fill)
        for position in required:
            state = self._positions.get(position)
            if state is not None:
                candidates.add(state.supplier)
                if state.uses is not None:
                    supplied_by_uses.append(state)
                if state.creator is not None and state.supplier != state.creator:
                    covered_creators.add(state.creator)
        if operation.empty is not None:
            state = self._positions[operation.empty]
            if state.uses is None:
                candidates.add(state.supplier)
            else:
                candidates.update(state.uses)
            if state.creator is not None and (
                state.uses is not None or state.supplier != state.creator
            ):
                covered_creators.add(state.creator)
        candidates.difference_update(covered_creators)
        covered: list[int] = []
        for state in supplied_by_uses:
            if state.supplier not in candidates:
                continue
            assert state.uses is not None  # noqa: S101 - Established when collected above.
            if len(candidates) <= MAX_SUPPLIER_SEARCH_CANDIDATES:
                follows_fill = not candidates.isdisjoint(state.uses)
            else:
                follows_fill = state.recent_use in candidates
            if follows_fill:
                covered.append(state.supplier)
        candidates.difference_update(covered)
        return candidates

    def _record(self, operation: Operation, occurrence: int, dependencies: set[int]):
        for position in operation.occupied:
            state = self._positions[position]
            if state.uses is None:
                state.uses = {occurrence}
            else:
                # Bounding this optional pruning keeps long references from
                # multiplying work by an arbitrarily large dependency count.
                if len(dependencies) <= MAX_PRUNING_CANDIDATES:
                    state.uses.difference_update(dependencies)
                state.uses.add(occurrence)
            state.recent_use = occurrence
        for position in (operation.fill, operation.empty):
            if position is None:
                continue
            state = self._positions.get(position)
            if state is None:
                self._positions[position] = _Position(occurrence)
            else:
                state.supplier = occurrence
                state.uses = None
                state.recent_use = None
        for position in operation.defines:
            self._positions[position] = _Position(occurrence, creator=occurrence)

    def add(self, operation: Operation) -> int:
        """Calculate and record one Create, Move, or Destroy."""
        candidates = self._collect(operation)
        dependencies = compare(self.graph, candidates)
        occurrence = self.graph.append(dependencies)
        self._record(operation, occurrence, candidates)
        return occurrence

    def simultaneous(self, operations: list[Operation]) -> list[int]:
        """Calculate vacancies belonging to one simultaneous destruction."""
        return [self.add(operation) for operation in operations]
