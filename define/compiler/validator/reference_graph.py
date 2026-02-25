"""Incremental cycle detection for global name references."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedCycle:
    """A rejected edge that would have closed a cycle, with the cycle path."""

    path: list[str]


class ReferenceGraph:
    """Directed graph of how definitions reference each other, with incremental cycle detection.

    Maintains a DAG of typed definition keys. When a new edge would close
    a cycle, it is rejected and the cycle path is returned. Edges that
    don't close a cycle are added to the graph.
    """

    def __init__(self):
        """Initialize an empty reference graph."""
        self._adjacency: dict[str, list[str]] = {}

    def try_add_edge(self, source: str, target: str) -> DetectedCycle | None:
        """Try to add an edge. Returns the detected cycle if it would close one.

        If the edge doesn't close a cycle, it is added to the graph and
        None is returned.
        """
        cycle = self._find_path(target, source)
        if cycle is not None:
            return DetectedCycle(path=[*cycle, target])
        self._adjacency.setdefault(source, []).append(target)
        return None

    def _find_path(self, start: str, end: str) -> list[str] | None:
        """Return a path from start to end (inclusive), or None if unreachable.

        Uses BFS to find the shortest path. Instead of copying the full path
        at every queue step, we record each node's predecessor in a dict and
        reconstruct the path only when we actually reach ``end``.
        """
        # Self-loop: the node trivially reaches itself.
        if start == end:
            return [start]
        # If start has no outgoing edges it can't reach anything.
        if start not in self._adjacency:
            return None
        # parent[node] = the node we came from. Doubles as the visited set:
        # a node is visited iff it is a key in parent.
        parent: dict[str, str] = {start: start}
        queue: deque[str] = deque([start])
        while queue:
            node = queue.popleft()
            for neighbor in self._adjacency.get(node, []):
                if neighbor == end:
                    # Found the target — walk the parent chain backwards
                    # to reconstruct start → ... → end.
                    path = [end]
                    cur = node
                    while cur != start:
                        path.append(cur)
                        cur = parent[cur]
                    path.append(start)
                    path.reverse()
                    return path
                if neighbor not in parent:
                    parent[neighbor] = node
                    queue.append(neighbor)
        return None
