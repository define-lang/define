"""The per-action operation dependency graph (DLP 44).

Every create, move, and destroy an action performs becomes a node. Edges encode
the spec's dependency rules for position operations (the section "Deterministic
Automatic Concurrency" in the spec).

A create or move that fires a triggered action is also tagged with that action,
so codegen can expand the operation into the callee's own graph and splice each
of its outputs' split points in for the caller operations that depend on them.

It is worth understanding the difference between this and the validator's other
mechanisms that track particle states, requirements, and guarantees: this data
structure is being built to support codegen, while most other data structures
exist to support validation.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from define.compiler import ast


@dataclass(frozen=True, slots=True, kw_only=True)
class OperationNode:
    """One operation in an action's dependency graph."""

    node_id: int
    # The position reference as written (the statement target).
    target: ast.PositionReference
    # The ids of the operations this node directly depends on (the operations
    # that must complete before it).
    depends_on: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateNode(OperationNode):
    """A body create in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveNode(OperationNode):
    """A body move of a particle from ``source`` to ``target``."""

    source: ast.PositionReference


@dataclass(frozen=True, slots=True, kw_only=True)
class DestroyNode(OperationNode):
    """A destroy of ``target``.

    A destroy statement or an auto-destruction at block end; one node covers the
    whole cascade.
    """


class OperationGraph:
    """An append-only dependency graph of one action's particle operations."""

    def __init__(self):
        """Create an empty graph."""
        self._nodes: list[OperationNode] = []
        # A position's canonical chained name -> id of the last operation on it,
        # for every position the body touches.
        self._last_operation: dict[tuple[str, ...], int] = {}
        # For each operation that fires triggered actions, the actions it fires.
        # Codegen expands the operation into those actions' own graphs. We support
        # triggering more than one action with a single operation because that's
        # possible with constructors and destructors.
        self._triggered_actions: dict[int, list[ast.ActionReference]] = {}

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order; a node's id is its index here."""
        return self._nodes

    def last_operation_node_id_for_key(self, key: tuple[str, ...]) -> int | None:
        """Return the last operation recorded under exactly this key, if any."""
        return self._last_operation.get(key)

    def triggered_actions(self, node_id: int) -> Sequence[ast.ActionReference]:
        """Return the triggered actions this operation fires (empty if none)."""
        return self._triggered_actions.get(node_id, ())

    def _add_dependencies(
        self,
        node_id: int,
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
        self._nodes[node_id].depends_on.extend(sorted(dependencies))

    def record_create(self, target: ast.PositionReference):
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        node_id = len(self._nodes)
        self._nodes.append(CreateNode(node_id=node_id, target=target))
        self._add_dependencies(node_id, (key,))
        self._last_operation[key] = node_id

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
        node_id = len(self._nodes)
        self._nodes.append(MoveNode(node_id=node_id, target=target, source=source))
        self._add_dependencies(
            node_id, (source_key, target_key), previously_touched_child_positions
        )
        self._last_operation[source_key] = node_id
        self._last_operation[target_key] = node_id

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
        node_id = len(self._nodes)
        self._nodes.append(DestroyNode(node_id=node_id, target=target))
        self._add_dependencies(node_id, (key,), previously_touched_child_positions)
        self._last_operation[key] = node_id

    def record_guarantees(
        self,
        trigger_node_id: int,
        guaranteed_positions: Iterable[tuple[str, ...]],
    ):
        """Point each contracted position's last operation at the trigger that guaranteed it."""
        for key in guaranteed_positions:
            self._last_operation[key] = trigger_node_id

    def record_action_trigger(
        self,
        node_id: int,
        action_chain: ast.ActionReference,
    ):
        """Record that operation ``node_id`` fires ``action_chain``."""
        self._triggered_actions.setdefault(node_id, []).append(action_chain)
