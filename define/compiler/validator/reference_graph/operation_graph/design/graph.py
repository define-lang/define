"""Compact append-only dependency storage and bounded reachability indexing."""

from __future__ import annotations

import array
import collections
from typing import final


@final
class Graph:
    """Store calculated dependencies without retaining transitive closure."""

    def __init__(self, cache_targets: int = 1024, cache_bytes: int = 64 * 1024**2):
        """Bound memoized expensive reachability questions independently of width."""
        self.offsets = array.array("Q", [0])
        self.edges = array.array("Q")
        self.heights = array.array("Q")
        self._first_consumer = array.array("q")
        self._next_consumer = array.array("q")
        self._consumers = array.array("Q")
        self._cache_targets = cache_targets
        self._cache_bytes = cache_bytes
        self._columns: collections.OrderedDict[int, bytearray] = (
            collections.OrderedDict()
        )
        self._column_bytes = 0
        self._expensive: collections.OrderedDict[int, int] = collections.OrderedDict()

    def __len__(self) -> int:
        """Count calculated operations."""
        return len(self.heights)

    def dependencies(self, operation: int) -> array.array[int]:
        """Read one operation's direct dependencies."""
        return self.edges[self.offsets[operation] : self.offsets[operation + 1]]

    def append(self, dependencies: list[int]) -> int:
        """Append an operation whose dependencies have already been calculated."""
        operation = len(self)
        height = 0
        for dependency in dependencies:
            dependency_height = self.heights[dependency] + 1
            if dependency_height > height:  # noqa: PLR1730 - Avoid a call per edge.
                height = dependency_height
            self._next_consumer.append(self._first_consumer[dependency])
            self._first_consumer[dependency] = len(self.edges)
            self._consumers.append(operation)
            self.edges.append(dependency)
        self.offsets.append(len(self.edges))
        self.heights.append(height)
        self._first_consumer.append(-1)
        return operation

    def _column(self, previous: int, following: int) -> bytearray:
        column = self._columns.pop(previous, bytearray())
        self._column_bytes -= len(column)
        required = max(len(column), following - previous + 1)
        while self._columns and (
            self._column_bytes + required > self._cache_bytes
            or len(self._columns) >= self._cache_targets
        ):
            _, removed = self._columns.popitem(last=False)
            self._column_bytes -= len(removed)
        column.extend(bytes(required - len(column)))
        column[0] = 2
        self._columns[previous] = column
        self._column_bytes += len(column)
        return column

    def _memoized_reaches(
        self, following: int, previous: int, column: bytearray
    ) -> bool:
        pending = [(following, self.offsets[following])]
        minimum_height = self.heights[previous]
        while pending:
            current, offset = pending[-1]
            if column[current - previous]:
                _ = pending.pop()
            elif offset == self.offsets[current + 1]:
                column[current - previous] = 1
            else:
                dependency = self.edges[offset]
                if dependency < previous:
                    pending[-1] = (current, offset + 1)
                elif column[dependency - previous] == 2:
                    column[current - previous] = 2
                elif (
                    column[dependency - previous] == 0
                    and self.heights[dependency] > minimum_height
                ):
                    pending.append((dependency, self.offsets[dependency]))
                else:
                    pending[-1] = (current, offset + 1)
        return column[following - previous] == 2

    def _repeated_expensive(self, previous: int) -> bool:
        count = self._expensive.pop(previous, 0) + 1
        if count >= 3:
            return True
        self._expensive[previous] = count
        if len(self._expensive) > 1024:
            _ = self._expensive.popitem(last=False)
        return False

    def reaches(self, following: int, previous: int) -> bool:
        """Test strict dependency reachability in the calculated graph."""
        if following <= previous or self.heights[following] <= self.heights[previous]:
            return False
        if self._first_consumer[previous] < 0:
            return False
        if previous in self._columns and following - previous < self._cache_bytes:
            return self._memoized_reaches(
                following, previous, self._column(previous, following)
            )
        backward = collections.deque([(following, self.offsets[following])])
        forward = collections.deque([(previous, self._first_consumer[previous])])
        earlier_seen = {following}
        later_seen = {previous}
        minimum_height = self.heights[previous]
        maximum_height = self.heights[following]
        consider_cache = (
            self._cache_targets > 0 and following - previous < self._cache_bytes
        )
        shared: int | None = None
        while backward and forward:
            if consider_cache and len(earlier_seen) + len(later_seen) >= 64:
                if (
                    shared is not None
                    and self._repeated_expensive(shared)
                    and self._memoized_reaches(
                        following, shared, self._column(shared, following)
                    )
                ):
                    return True
                if self._repeated_expensive(previous):
                    return self._memoized_reaches(
                        following, previous, self._column(previous, following)
                    )
                consider_cache = False
            current, offset = backward[0]
            if offset == self.offsets[current + 1]:
                _ = backward.popleft()
            else:
                dependency = self.edges[offset]
                backward[0] = (current, offset + 1)
                if dependency in later_seen:
                    return True
                if (
                    self.heights[dependency] > minimum_height
                    and dependency > previous
                    and dependency not in earlier_seen
                ):
                    earlier_seen.add(dependency)
                    backward.append((dependency, self.offsets[dependency]))
            current, offset = forward[0]
            if offset < 0:
                _ = forward.popleft()
            else:
                consumer = self._consumers[offset]
                forward[0] = (current, self._next_consumer[offset])
                if consumer in earlier_seen:
                    return True
                if (
                    self.heights[consumer] < maximum_height
                    and consumer < following
                    and consumer not in later_seen
                ):
                    later_seen.add(consumer)
                    if (
                        consumer in self._columns
                        and following - consumer < self._cache_bytes
                    ):
                        if self._memoized_reaches(
                            following, consumer, self._column(consumer, following)
                        ):
                            return True
                    else:
                        if (
                            consider_cache
                            and shared is None
                            and self.offsets[consumer + 1] - self.offsets[consumer] > 1
                        ):
                            shared = consumer
                        forward.append((consumer, self._first_consumer[consumer]))
        return False
