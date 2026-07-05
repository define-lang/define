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
    # The ids of the operations this node directly depends on (the operations
    # that must complete before it).
    depends_on: list[int] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionOperationNode(OperationNode):
    """An operation the body performs on a written position."""

    # The position reference as written (the statement target).
    target: ast.PositionReference


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateNode(PositionOperationNode):
    """A body create in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveNode(PositionOperationNode):
    """A body move of a particle from ``source`` to ``target``."""

    source: ast.PositionReference


@dataclass(frozen=True, slots=True, kw_only=True)
class DestroyNode(PositionOperationNode):
    """A destroy of ``target``.

    A destroy statement or an auto-destruction at block end; one node covers the
    whole cascade.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class GuaranteeNode(OperationNode):
    """A triggered action's output, produced inside the callee.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that fired the trigger; codegen resolves
    this node to the callee's last operation on ``output_position`` when it
    splices ``action`` in at that trigger. Caller operations that read the output
    depend on this node with ordinary edges.
    """

    # The triggered action's full typed name (the key of the callee's graph).
    action: str
    # The callee's own position key for the output.
    output_position: tuple[str, ...]


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
            # Ancestor Rule: the most recent operation on the position itself or
            # any of its ancestors.
            ancestor_chain = self._most_recent_ancestor_chain_operation(key)
            if ancestor_chain is not None:
                dependencies.add(ancestor_chain)
        # Child Rule: a move or destroy also depends on the last operation on
        # each touched transitive child of the position it empties.
        for child_key in previously_touched_child_positions:
            child = self._last_operation.get(child_key)
            if child is not None:
                dependencies.add(child)
        self._nodes[node_id].depends_on.extend(sorted(dependencies))

    def _most_recent_ancestor_chain_operation(self, key: tuple[str, ...]) -> int | None:
        """Return the most recent operation on ``key`` or any of its ancestors."""
        most_recent = None
        for length in range(len(key), 0, -1):
            operation = self._last_operation.get(key[:length])
            if operation is not None and (
                most_recent is None or operation > most_recent
            ):
                most_recent = operation
        return most_recent

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
        action: str,
        outputs: Iterable[tuple[tuple[str, ...], tuple[str, ...]]],
    ):
        """Record a triggered action's outputs as guarantee nodes hanging off the trigger.

        Each ``outputs`` pair is a contracted position's absolute key and the
        callee's own key for it. The absolute position's last operation becomes a
        new guarantee node, so caller operations that read it depend on the
        callee's split point rather than on the trigger operation itself.
        """
        for absolute_key, output_position in outputs:
            node_id = len(self._nodes)
            self._nodes.append(
                GuaranteeNode(
                    node_id=node_id,
                    action=action,
                    output_position=output_position,
                    depends_on=[trigger_node_id],
                )
            )
            self._last_operation[absolute_key] = node_id

    def record_action_trigger(
        self,
        node_id: int,
        action_chain: ast.ActionReference,
    ):
        """Record that operation ``node_id`` fires ``action_chain``."""
        self._triggered_actions.setdefault(node_id, []).append(action_chain)
