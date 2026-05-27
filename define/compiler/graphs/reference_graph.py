"""Directed graph of definition references, backed by networkx."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import cast

import networkx as nx

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

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


@dataclass(frozen=True)
class DetectedCycle:
    """A rejected edge that would have closed a cycle, with the cycle path."""

    path: list[str]


class ReferenceGraph:
    """Directed graph of how definitions reference each other, with incremental cycle detection.

    Maintains a DAG of typed definition keys. When a new edge would close
    a cycle, it is rejected and the cycle path is returned. Edges that
    don't close a cycle are added to the graph.

    Each node stores its ``QualityDefinition`` as a node attribute.
    """

    def __init__(self):
        """Initialize an empty reference graph."""
        self._graph: nx.DiGraph[str] = nx.DiGraph()

    def add_definition(self, definition: ast.QualityDefinition):
        """Register a definition as a node in the graph."""
        self._graph.add_node(
            definition.typed_name.source_typed_name, definition=definition
        )

    def try_add_edge(self, edge: ReferenceEdge) -> DetectedCycle | None:
        """Try to add an edge. Returns the detected cycle if it would close one.

        If the edge doesn't close a cycle, it is added to the graph and
        None is returned. The source node's definition is stored as a
        node attribute.
        """
        source = edge.source_full_typed_name
        target = edge.target_full_typed_name
        if source == target:
            return DetectedCycle(path=[source, target])
        # A brand-new target node has no outgoing edges, so it can't
        # create a path back to source — skip the cycle check.
        if target not in self._graph:
            self._graph.add_node(target)
        elif nx.has_path(self._graph, target, source):
            cycle_path = nx.shortest_path(self._graph, target, source)  # pyright: ignore[reportUnknownMemberType]
            return DetectedCycle(path=[*cycle_path, target])
        _ = self._graph.add_edge(source, target)
        return None

    def dfs_postorder_from(
        self, root: ast.QualityDefinition
    ) -> Iterator[ast.QualityDefinition]:
        """Yield definitions in DFS post-order from root.

        Leaf nodes are yielded first, root last.
        """
        root_key = root.typed_name.source_typed_name
        for node_key in nx.dfs_postorder_nodes(self._graph, root_key):
            yield cast(
                "ast.QualityDefinition", self._graph.nodes[node_key]["definition"]
            )

    def dfs_postorder_all(self) -> Iterator[ast.QualityDefinition]:
        """Yield all definitions in DFS post-order, handling disconnected components."""
        for node_key in nx.dfs_postorder_nodes(self._graph):
            node_data = self._graph.nodes[node_key]
            if "definition" in node_data:
                yield cast("ast.QualityDefinition", node_data["definition"])
