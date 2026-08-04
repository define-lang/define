"""Action call graph for tracking trigger relationships between actions."""

# TODO: Delete this module once destructors are fully implemented in the
# operation graph, including destruction contracts. It survives only so tests
# can assert destructor firing, which the operation graph does not yet represent
# (a destroy and its destructor cascade are still a single atomic node, and
# caller-attached destructors from destruction contracts are not recorded there
# at all). Once the operation graph carries that firing information, these
# assertions move to action_graph()/action_graph_set() and this module goes away.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionGraphEdge:
    """A directed edge from a source action to a target action it triggers."""

    source: str
    target: str


class ActionCallGraph:
    """Tracks which actions can trigger which other actions.

    Built during the DFS post-order walk of the reference graph.
    Edges are collected by the per-definition validators and added
    by the ReferenceGraphValidator after each definition is analyzed.
    """

    def __init__(self):
        """Initialize an empty call graph."""
        # The same trigger edge can be added more than once, so successors are
        # counted rather than listed.
        self._successor_counts: dict[str, dict[str, int]] = {}

    def add_edge(self, source: str, target: str):
        """Add a directed trigger edge from source to target."""
        successor_counts = self._successor_counts.setdefault(source, {})
        _ = self._successor_counts.setdefault(target, {})
        successor_counts[target] = successor_counts.get(target, 0) + 1

    def unique_edges(self) -> set[tuple[str, str]]:
        """Return the set of distinct ``(source, target)`` pairs."""
        unique: set[tuple[str, str]] = set()
        for source, successor_counts in self._successor_counts.items():
            for target in successor_counts:
                unique.add((source, target))
        return unique

    def edges(self) -> list[tuple[str, str]]:
        """Return every trigger edge as a ``(source, target)`` tuple, grouped by source.

        Sources appear in the order they were first seen, and each source's
        targets in the order they were first seen for that source.
        """
        edges: list[tuple[str, str]] = []
        for source, successor_counts in self._successor_counts.items():
            for target, count in successor_counts.items():
                edges.extend([(source, target)] * count)
        return edges
