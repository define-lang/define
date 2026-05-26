"""Action call graph for tracking trigger relationships between actions."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


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

    _graph: nx.MultiDiGraph[str]

    def __init__(self):
        """Initialize an empty call graph."""
        self._graph = nx.MultiDiGraph()

    def add_edge(self, source: str, target: str):
        """Add a directed trigger edge from source to target."""
        _ = self._graph.add_edge(source, target)

    def unique_edges(self) -> set[tuple[str, str]]:
        """Return the set of distinct ``(source, target)`` pairs."""
        return {(source, target) for source, target in self._graph.edges()}

    def edges(self) -> list[tuple[str, str]]:
        """Return every trigger edge as a ``(source, target)`` tuple, in insertion order."""
        return list(self._graph.edges())
