"""The per-action operation dependency graph (DLP 44).

Every create, move, and destroy an action performs becomes a node. Edges encode
the spec's dependency rules for position operations (the section "Deterministic
Automatic Concurrency" in the spec).
"""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from define.compiler import ast


class OperationKind(enum.Enum):
    """What a node in the operation graph represents."""

    CREATE = enum.auto()
    MOVE = enum.auto()
    # A destroy statement or an auto-destruction at block end. One node covers
    # the whole cascade.
    DESTROY = enum.auto()


@dataclass(frozen=True, slots=True)
class OperationNode:
    """One operation in an action's dependency graph."""

    node_id: int
    kind: OperationKind
    # The position reference as written (the statement target).
    target: ast.PositionReference
    # MOVE only: the particle's source position.
    source: ast.PositionReference | None = None
    # The ids of the operations this node directly depends on (the operations
    # that must complete before it).
    depends_on: list[int] = field(default_factory=list)


class OperationGraph:
    """An append-only dependency graph of one action's particle operations."""

    def __init__(self):
        """Create an empty graph."""
        self._nodes: list[OperationNode] = []
        # A position's canonical chained name -> id of the last operation on it,
        # for every position the body touches.
        self._last_operation: dict[tuple[str, ...], int] = {}

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order; a node's id is its index here."""
        return self._nodes

    def last_operation_identifier_for_key(self, key: tuple[str, ...]) -> int | None:
        """Return the last operation recorded under exactly this key, if any."""
        return self._last_operation.get(key)

    def _add_node(
        self,
        kind: OperationKind,
        target: ast.PositionReference,
        *,
        source: ast.PositionReference | None = None,
    ) -> int:
        identifier = len(self._nodes)
        self._nodes.append(
            OperationNode(
                node_id=identifier,
                kind=kind,
                target=target,
                source=source,
            )
        )
        return identifier

    def _add_dependencies(
        self,
        identifier: int,
        positions: Iterable[tuple[str, ...]],
        previously_touched_child_positions: Iterable[tuple[str, ...]] = (),
    ):
        """Create edges from previous operations to this node."""
        # A single predecessor can be reached more than once (a move reads both
        # its source and target, a destroy depends on every previous child
        # operation including possibly duplicate parents), so the dependencies
        # are collected in a set before being stored.
        dependencies: set[int] = set()
        for key in positions:
            # Rule 1: the previous operation on the same position.
            same_position = self._last_operation.get(key)
            if same_position is not None:
                dependencies.add(same_position)
            # Rule 2: the last operation on the nearest recorded ancestor.
            for length in range(len(key) - 1, 0, -1):
                ancestor = self._last_operation.get(key[:length])
                if ancestor is not None:
                    dependencies.add(ancestor)
                    break
        # Rule 3: the last operation on each touched transitive child.
        for child_key in previously_touched_child_positions:
            child = self._last_operation.get(child_key)
            if child is not None:
                dependencies.add(child)
        self._nodes[identifier].depends_on.extend(sorted(dependencies))

    def record_create(self, target: ast.PositionReference):
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        identifier = self._add_node(OperationKind.CREATE, target)
        self._add_dependencies(identifier, (key,))
        self._last_operation[key] = identifier

    def record_move(
        self,
        source: ast.PositionReference,
        target: ast.PositionReference,
        previously_touched_child_positions: Iterable[tuple[str, ...]],
    ):
        """Record a body move from ``source`` to ``target``.

        ``previously_touched_child_positions`` are the keys in the source's trie
        subtree (occupied or known-empty) at the moment of the move.
        """
        source_key = source.canonical_chained_name_tuple
        target_key = target.canonical_chained_name_tuple
        identifier = self._add_node(OperationKind.MOVE, target, source=source)
        self._add_dependencies(
            identifier, (source_key, target_key), previously_touched_child_positions
        )
        self._last_operation[source_key] = identifier
        self._last_operation[target_key] = identifier

    def record_destroy(
        self,
        target: ast.PositionReference,
        previously_touched_child_positions: Iterable[tuple[str, ...]],
    ):
        """Record a destroy of ``target``.

        The single node covers the whole cascade: everything the destroy also
        removes, and everything the fired destructors read, is a transitive
        child of ``target`` and comes in through ``previously_touched_child_positions``.
        """
        key = target.canonical_chained_name_tuple
        identifier = self._add_node(OperationKind.DESTROY, target)
        self._add_dependencies(identifier, (key,), previously_touched_child_positions)
        self._last_operation[key] = identifier
