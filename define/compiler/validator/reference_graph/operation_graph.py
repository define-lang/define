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
from dataclasses import dataclass

from define.compiler import ast

if typing.TYPE_CHECKING:
    from collections.abc import Container, Iterable, Sequence


@dataclass(frozen=True, slots=True, kw_only=True)
class OperationNode:
    """One operation in an action's dependency graph."""

    node_id: int
    # The ids of the operations this node directly depends on (the operations
    # that must complete before it).
    depends_on: list[int]


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementNode(OperationNode):
    """A caller-controlled contracted position an operation needs in a given state.

    This stands in for the caller operation that satisfies an inferred requirement.
    The renderer/codegen resolves it to the caller op that most recently operated
    on ``requirement_position`` before the trigger. It carries only the position,
    not the required state, because that most-recent caller op already leaves the
    position in the required state in all valid Define programs.
    """

    # This action's own key for the caller-controlled contracted position.
    requirement_position: tuple[str, ...]

    def caller_key(self, caller_chain: tuple[str, ...]) -> tuple[str, ...]:
        """Return this requirement's absolute key in a caller that triggers it via ``caller_chain``."""
        return ast.chain_in_caller(caller_chain, self.requirement_position)


class OperationGraph:
    """An append-only dependency graph of one action's particle operations."""

    def __init__(self, requirements: Container[tuple[str, ...]]):
        """Create an empty graph.

        ``requirements`` is the validator's inferred-requirements map, shared by
        reference: it is empty at construction and fills in as the body is
        analyzed, one requirement recorded just before the operation that needs it.
        """
        self._nodes: list[OperationNode] = []
        # A position's canonical chained name -> id of the last operation on it,
        # for every position the body touches.
        # TODO: Experiment with cheaper structures for this. Today
        # _most_recent_ancestor_chain_operation walks every prefix of a position,
        # so the flat dict makes it slice and re-hash a fresh tuple per ancestor
        # (O(depth^2), and those keys are long typed-name strings). Some options
        # worth trying, not a decided plan:
        #   - A prefix trie keyed by single chain elements: keeps the ancestor
        #     walk O(depth) but with single-element steps, each element hashed
        #     once and no throwaway tuples, while still serving exact-key point
        #     lookups.
        #   - A path-max structure: the query is "max op id over the root->node
        #     path" with point updates, and since op ids increase monotonically,
        #     recording an op at P is really a subtree-assign of the new max. A
        #     static tree makes this O(log n) via Euler tour + a lazy segment
        #     tree, but our position tree is built incrementally, so it would take
        #     a dynamic-tree structure (Euler-tour / link-cut) whose constant
        #     probably loses to a tight walk at the small depths we see.
        #   - A last-op fast path: remember the previous op's (position, id); when
        #     the next query is inside that position's subtree, that id is the
        #     answer in ~O(1) (it is the global max and an ancestor), falling back
        #     to the walk otherwise. Covers the common operate-parent-then-child
        #     pattern. (Caching more broadly does not help: every ordinary op is a
        #     new global max, so it invalidates the answer for its whole subtree,
        #     not just when a requirement node is added.)
        self._last_operation: dict[tuple[str, ...], int] = {}
        # For each operation that fires triggered actions, the actions it fires.
        # Codegen expands the operation into those actions' own graphs. We support
        # triggering more than one action with a single operation because that's
        # possible with constructors and destructors.
        self._triggered_actions: dict[int, list[ast.ActionReference]] = {}
        self._requirements: Container[tuple[str, ...]] = requirements

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order; a node's id is its index here."""
        return self._nodes

    def last_operation_node_id_for_key(self, key: tuple[str, ...]) -> int | None:
        """Return the last operation recorded under exactly this key, if any."""
        return self._last_operation.get(key)

    def body_touched_key(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly this key.

        A materialized RequirementNode stands in for a caller operation, not a
        body operation, so it does not count as the body touching the position.
        """
        node_id = self._last_operation.get(key)
        return node_id is not None and not isinstance(
            self._nodes[node_id], RequirementNode
        )

    def triggered_actions(self, node_id: int) -> Sequence[ast.ActionReference]:
        """Return the triggered actions this operation fires (empty if none)."""
        return self._triggered_actions.get(node_id, ())

    def _compute_dependencies(
        self,
        fill_position: tuple[str, ...] | None = None,
        empty_position: tuple[str, ...] | None = None,
        previously_touched_child_positions: Iterable[tuple[str, ...]] = (),
    ) -> list[int]:
        """Return the ids this operation depends on.

        Materializes any requirements nodes this operation may depend on.
        """
        # A move fills its target and empties its source, so a single predecessor
        # can be reached twice; the dependencies are collected in a set first.
        dependencies: set[int] = set()
        # Fill Rule: filling a position waits on the most recent operation on
        # that position and its parents, so the parent is present to hold it.
        if fill_position is not None:
            filled_ancestor = self._most_recent_ancestor_chain_operation(fill_position)
            if filled_ancestor is not None:
                dependencies.add(filled_ancestor)
        # Empty Rule: emptying a position waits on the most recent operation in
        # each touched child position (minus a shallower one a deeper touched
        # position has already superseded), and on the emptied position's own
        # chain only when that is more recent than every one of those child
        # operations -- otherwise a child already reaches it.
        child_operations = self._surviving_child_operations(
            previously_touched_child_positions
        )
        dependencies.update(child_operations)
        if empty_position is not None:
            emptied_ancestor = self._most_recent_ancestor_chain_operation(
                empty_position
            )
            if emptied_ancestor is not None and all(
                emptied_ancestor > child_operation
                for child_operation in child_operations
            ):
                dependencies.add(emptied_ancestor)
        return sorted(dependencies)

    def _most_recent_ancestor_chain_operation(
        self, position: tuple[str, ...]
    ) -> int | None:
        """Return the most recent operation on ``position``'s ancestor chain, materializing requirements as needed.

        One shallow-to-deep pass, tracking the most recent operation seen so far
        as ``ancestor``. An empty contracted position is caller territory and gets
        a RequirementNode -- but only when no real operation above has established
        it, which is exactly when ``ancestor`` is absent or is itself a
        RequirementNode (a real operation always outranks the requirement nodes on
        its chain). Each new node depends on ``ancestor`` via the Fill Rule. The
        returned id is the fill/empty dependency.
        """
        ancestor: int | None = None
        for length in range(1, len(position) + 1):
            key = position[:length]
            existing = self._last_operation.get(key)
            if existing is not None:
                if ancestor is None or existing > ancestor:
                    ancestor = existing
                continue
            if key not in self._requirements or (
                ancestor is not None
                and not isinstance(self._nodes[ancestor], RequirementNode)
            ):
                continue
            node_id = len(self._nodes)
            self._nodes.append(
                RequirementNode(
                    node_id=node_id,
                    requirement_position=key,
                    depends_on=[ancestor] if ancestor is not None else [],
                )
            )
            self._last_operation[key] = node_id
            ancestor = node_id
        return ancestor

    def _surviving_child_operations(
        self, touched_child_positions: Iterable[tuple[str, ...]]
    ) -> set[int]:
        """Return the touched child operations that no deeper touched one supersedes."""
        # Touched positions without an operation never survive or suppress
        # anything, so only the ones carrying an operation matter. This is almost
        # always a single position (the one particle inside what is being emptied)
        # or none, so the supersession search below is over a tiny set.
        operated_positions = [
            (key, operation)
            for key in touched_child_positions
            if (operation := self._last_operation.get(key)) is not None
        ]
        # With no deeper touched position to supersede it, a lone operation always
        # survives, so the overwhelmingly common empty/single case needs no search.
        if len(operated_positions) <= 1:
            return {operation for _, operation in operated_positions}
        # A touched child whose subtree holds a more recent operation is dropped:
        # that deeper operation already waits on it, so a direct edge is redundant.
        # The nested scan is quadratic in the number of operated positions, but
        # that count is the breadth of a single destroy or move cascade -- the
        # particles nested inside the one position being emptied -- which is a
        # handful at most, so a flat scan beats building an index over it.
        survivors: set[int] = set()
        for key, operation in operated_positions:
            depth = len(key)
            superseded = False
            for deeper_key, deeper_operation in operated_positions:
                # A position is never a strict descendant of itself (its key is
                # not longer), so it never suppresses itself or a duplicate.
                if (
                    len(deeper_key) > depth
                    and deeper_operation >= operation
                    and deeper_key[:depth] == key
                ):
                    superseded = True
                    break
            if not superseded:
                survivors.add(operation)
        return survivors

    def record_create(self, target: ast.PositionReference):
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        depends_on = self._compute_dependencies(fill_position=key)
        node_id = len(self._nodes)
        self._nodes.append(
            CreateNode(node_id=node_id, target=target, depends_on=depends_on)
        )
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
        depends_on = self._compute_dependencies(
            fill_position=target_key,
            empty_position=source_key,
            previously_touched_child_positions=previously_touched_child_positions,
        )
        node_id = len(self._nodes)
        self._nodes.append(
            MoveNode(
                node_id=node_id, target=target, source=source, depends_on=depends_on
            )
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
        depends_on = self._compute_dependencies(
            empty_position=key,
            previously_touched_child_positions=previously_touched_child_positions,
        )
        node_id = len(self._nodes)
        self._nodes.append(
            DestroyNode(node_id=node_id, target=target, depends_on=depends_on)
        )
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
