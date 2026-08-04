"""Directed graph of definition references."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from define.compiler import ast


@dataclass(frozen=True, slots=True)
class ReferenceEdge:
    """A reference from one definition to a global name in another file."""

    enclosing_definition: ast.QualityDefinition
    global_name_reference: ast.GlobalTypedNameReference

    @property
    def target_full_typed_name(self) -> str:
        """Return the fully qualified typed-name key for this edge target."""
        return self.global_name_reference.full_typed_name

    @property
    def source_full_typed_name(self) -> str:
        """Return the fully qualified typed-name key for the edge source."""
        return self.enclosing_definition.typed_name.source_typed_name


# The typed names a rejected edge would have formed a cycle through, in the
# order the references run, beginning and ending at the same name.
type DetectedCycle = list[str]


class ReferenceGraph:
    """Directed graph of how definitions reference each other, with incremental cycle detection.

    Maintains a DAG of typed definition keys. When a new edge would close
    a cycle, it is rejected and the shortest cycle path is returned. Edges
    that don't close a cycle are added to the graph.

    Each node registered by ``add_definition`` also stores its
    ``QualityDefinition``.
    """

    def __init__(self):
        """Initialize an empty reference graph."""
        # Neighbors are dict keys rather than list entries so that repeating the
        # same reference costs nothing, while iteration still follows the order
        # in which neighbors were first seen.
        self._successors: dict[str, dict[str, None]] = {}
        # A node's depth is kept below the depth of everything it references,
        # so an edge whose endpoints already satisfy that cannot close a cycle
        # and is settled without searching the graph. The rest are settled by
        # walking forward from the target, which is why no reverse adjacency is
        # kept: a reverse map costs about 74 bytes per edge, some 1.1 GB for
        # five million definitions averaging three references each.
        self._depths: dict[str, int] = {}
        self._definitions: dict[str, ast.QualityDefinition] = {}

    def add_definition(self, definition: ast.QualityDefinition):
        """Register a definition as a node in the graph."""
        node_key = definition.typed_name.source_typed_name
        self._add_node(node_key)
        self._definitions[node_key] = definition

    def try_add_edge(self, edge: ReferenceEdge) -> DetectedCycle | None:
        """Try to add an edge. Returns the detected cycle if it would close one.

        If the edge doesn't close a cycle, it is added to the graph.
        """
        source = edge.source_full_typed_name
        target = edge.target_full_typed_name
        if source == target:
            return [source, target]
        self._add_node(source)
        if target not in self._successors:
            # A brand-new target node has no outgoing edges, so it can't
            # create a path back to source — skip the cycle check.
            self._successors[target] = {}
            self._depths[target] = self._depths[source] + 1
        elif self._depths[source] >= self._depths[target] and self._deepen(
            source, target
        ):
            return [*self._shortest_path(target, source), target]
        self._successors[source][target] = None
        return None

    def dfs_postorder_from(
        self, root: ast.QualityDefinition
    ) -> Iterator[ast.QualityDefinition]:
        """Yield definitions in DFS post-order from root.

        Leaf nodes are yielded first, root last.
        """
        root_key = root.typed_name.source_typed_name
        for node_key in self._dfs_postorder([root_key]):
            yield self._definitions[node_key]

    def dfs_postorder_all(self) -> Iterator[ast.QualityDefinition]:
        """Yield all definitions in DFS post-order, handling disconnected components."""
        for node_key in self._dfs_postorder(self._successors):
            if node_key in self._definitions:
                yield self._definitions[node_key]

    def _add_node(self, node_key: str):
        if node_key not in self._successors:
            self._successors[node_key] = {}
            self._depths[node_key] = 0

    def _deepen(self, source: str, target: str) -> bool:
        """Push target below source in the depth order, reporting a cycle.

        Returns True when target already reaches source, in which case every
        depth this changed is restored before returning.
        """
        successors = self._successors
        depths = self._depths
        previous_depths: dict[str, int] = {}
        pending = [(target, depths[source] + 1)]
        while pending:
            node_key, new_depth = pending.pop()
            if new_depth <= depths[node_key]:
                continue
            if node_key not in previous_depths:
                previous_depths[node_key] = depths[node_key]
            depths[node_key] = new_depth
            for successor_key in successors[node_key]:
                if successor_key == source:
                    for restored_key, previous_depth in previous_depths.items():
                        depths[restored_key] = previous_depth
                    return True
                if depths[successor_key] <= new_depth:
                    pending.append((successor_key, new_depth + 1))
        return False

    def _shortest_path(self, from_key: str, to_key: str) -> list[str]:
        """Return the shortest path between two nodes, which must be connected."""
        successors = self._successors
        path_predecessors: dict[str, str | None] = {from_key: None}
        frontier: list[str] = [from_key]
        while frontier and to_key not in path_predecessors:
            current_frontier = frontier
            frontier = []
            for node_key in current_frontier:
                for successor_key in successors[node_key]:
                    if successor_key not in path_predecessors:
                        path_predecessors[successor_key] = node_key
                        frontier.append(successor_key)
        return _build_path(path_predecessors, to_key)

    def _dfs_postorder(self, start_keys: Iterable[str]) -> Iterator[str]:
        """Yield every node reachable from start_keys in DFS post-order."""
        visited: set[str] = set()
        for start_key in start_keys:
            if start_key in visited:
                continue
            visited.add(start_key)
            stack = [(start_key, iter(self._successors[start_key]))]
            while stack:
                node_key, successor_keys = stack[-1]
                for successor_key in successor_keys:
                    if successor_key not in visited:
                        visited.add(successor_key)
                        stack.append(
                            (successor_key, iter(self._successors[successor_key]))
                        )
                        break
                else:
                    _ = stack.pop()
                    yield node_key


def _build_path(path_predecessors: dict[str, str | None], end_key: str) -> list[str]:
    path: list[str] = []
    walk_key: str | None = end_key
    while walk_key is not None:
        path.append(walk_key)
        walk_key = path_predecessors[walk_key]
    path.reverse()
    return path
