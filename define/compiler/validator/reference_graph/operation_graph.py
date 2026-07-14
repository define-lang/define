"""The per-action operation dependency graph (DLP 44).

Every create, move, and destroy an action performs becomes a node. Edges encode
the spec's dependency rules for position operations (the section "Deterministic
Automatic Concurrency" in the spec).

The graph also holds nodes that represent requirements and guarantees, to allow
splicing graphs together (connecting a caller's operation to the actual operations
it triggers in the callee).

It is worth understanding the difference between this and the validator's other
mechanisms that track particle states, requirements, and guarantees: this data
structure is being built to support codegen, while most other data structures
exist to support validation.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RequirementSatisfaction:
    """One requirement of one trigger of a callee, satisfied by the operation that carries this.

    Codegen, reaching the operation while walking, splices the matching
    RequirementNode of the callee's graph here. A callee appears in some
    operation's satisfactions exactly once per trigger, since the operation
    that fills the trigger position satisfies the requirement on it.

    TODO: Remove this, along with OperationNode.satisfies, once both renderers
    read the triggers instead. An ActionTrigger says the same thing from the
    other side: its callee and trigger_node_id are these, and the node this would
    hang off is the one its satisfiers map the requirement to.
    """

    # The triggered callee, which is also the key of its graph. Which particle's
    # action ran is not recorded here: the operation that fired the trigger
    # names the trigger position, whose chain says which one.
    callee: ast.GlobalTypedNameReference
    # The callee's own key for the requirement this operation satisfies.
    requirement_position: tuple[str, ...]
    # The operation that fired this trigger, which is what tells the
    # satisfactions of one trigger of a callee from those of the next: an
    # action can trigger the same callee any number of times, and one operation
    # can satisfy the same requirement for more than one of those triggers.
    trigger_node_id: int


@dataclass(frozen=True, slots=True)
class ActionTrigger:
    """One triggering of a callee, and what satisfies each requirement of the callee.

    Recorded from the caller's side, at the moment it triggers, because only the
    caller knows what it did to the positions the callee names.
    """

    # The callee this triggering fires.
    callee: ast.GlobalTypedNameReference
    # The operation that triggered the callee.
    trigger_node_id: int
    # The node that satisfies each requirement of the callee, by the callee's own
    # key for that requirement. The node is either an operation of this action, or
    # one of this action's own requirement nodes, which is how a requirement this
    # action does not satisfy itself passes up to its own caller.
    satisfiers: dict[tuple[str, ...], int]


@dataclass(frozen=True, slots=True, kw_only=True)
class OperationNode:
    """One operation in an action's dependency graph."""

    node_id: int
    # The ids of the operations this node directly depends on (the operations
    # that must complete before it).
    depends_on: list[int]
    # Requirements of triggered callees this operation satisfies. Back-populated
    # when a callee is triggered. A RequirementNode or GuaranteeNode can carry
    # these too, which is what makes empty-by-default-via-parent and
    # multi-level pass-through work.
    satisfies: list[RequirementSatisfaction] = field(default_factory=list)


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
    """A position a triggered action guarantees, which the callee itself operates on.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that fired the trigger; codegen resolves
    this node to the callee's last operation on ``guaranteed_position`` when it
    splices ``action`` in at that trigger. Caller operations that read the
    position depend on this node with ordinary edges.
    """

    # The triggered action's full typed name (the key of the callee's graph).
    action: str
    # The guaranteed position, by the callee's own key for it.
    guaranteed_position: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementNode(OperationNode):
    """A caller-controlled contracted position an operation needs in a given state.

    This stands in for the caller operation that satisfies an inferred requirement.
    The renderer/codegen resolves it to the caller op that most recently operated
    on ``requirement_position`` before the trigger. A position can be empty
    without any operation emptying it, so an empty requirement can have no such
    caller op at all, which is why the required state is recorded here.
    """

    # The state this action needs the position to be in.
    required_state: action_contract.PositionOccupancyState
    # This action's own key for the caller-controlled contracted position.
    # TODO: Remove this once the old operation_graph_renderer, its last reader,
    # is gone. A caller that holds a satisfaction reaches the node through
    # requirement_node(), so nothing else has to read a position back off a node.
    # Inverting the old renderer needs a lookup that tolerates a position no
    # requirement node stands for, which is why it still reads this.
    requirement_position: tuple[str, ...] = field(default=(), compare=False)


class OperationGraph:
    """An append-only dependency graph of one action's particle operations."""

    def __init__(
        self,
        requirements: Mapping[tuple[str, ...], action_contract.PositionRequirement],
        trigger_position: ast.PositionReference | None = None,
    ):
        """Create an empty graph.

        ``requirements`` is the validator's inferred-requirements map, shared by
        reference: it is empty at construction and fills in as the body is
        analyzed, one requirement recorded just before the operation that needs it.
        ``trigger_position`` is this action's own trigger position: the body reads
        it filled without an operation of its own, so like a requirement it gets a
        RequirementNode standing in for the caller op that fired the trigger.
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
        self._requirements: Mapping[
            tuple[str, ...], action_contract.PositionRequirement
        ] = requirements
        self._trigger_position_key: tuple[str, ...] = (
            trigger_position.canonical_chained_name_tuple
            if trigger_position is not None
            else ()
        )
        # A requirement's position -> the RequirementNode for that position.
        self._requirement_nodes: dict[tuple[str, ...], RequirementNode] = {}
        # Every triggering this action performs, in the order it performs them.
        # One operation can fire more than one (creating a particle fires every
        # constructor it has).
        self._triggers: list[ActionTrigger] = []
        # Every action gets an occupied requirement on the position that triggers
        # it. This simplifies splicing together graphs, because the satisfaction
        # of the trigger always has a requirement to map to. A constructor or
        # destructor gets a RequirementNode with an empty key as a symbolic stand-in
        # for "the action got triggered."
        self._trigger_position_requirement_node_id: int = self._add_requirement_node(
            self._trigger_position_key,
            ancestor=None,
            required_state=action_contract.PositionOccupancyState.OCCUPIED,
        )

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order; a node's id is its index here."""
        return self._nodes

    def requirement_node(
        self, requirement_position: tuple[str, ...]
    ) -> RequirementNode:
        """Return the RequirementNode on the named position."""
        return self._requirement_nodes[requirement_position]

    @property
    def trigger_position_key(self) -> tuple[str, ...]:
        """This action's own trigger position key; empty for a constructor/destructor."""
        return self._trigger_position_key

    def last_operation_affecting_position(self, key: tuple[str, ...]) -> int:
        """Return the last operation that affected the position at ``key``.

        An operation recorded under exactly this key wins. Otherwise, a move of
        an ancestor position affected this one, because a move relocates every
        position inside what it moves. Any other ancestor operation did not (a
        create makes exactly one particle; the positions inside it start empty),
        so a position nothing affected raises KeyError.
        """
        operation = self._last_operation.get(key)
        if operation is not None:
            return operation
        ancestor = self._most_recent_existing_ancestor_operation(key)
        if ancestor is not None and isinstance(self._nodes[ancestor], MoveNode):
            return ancestor
        raise KeyError(key)

    def _most_recent_existing_ancestor_operation(
        self, key: tuple[str, ...]
    ) -> int | None:
        """Return the most recent already-recorded operation on ``key``'s ancestor chain."""
        most_recent: int | None = None
        for length in range(len(key) - 1, 0, -1):
            operation = self._last_operation.get(key[:length])
            if operation is not None and (
                most_recent is None or operation > most_recent
            ):
                most_recent = operation
        return most_recent

    def body_touched_key(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly this key.

        A materialized RequirementNode stands in for a caller operation, not a
        body operation, so it does not count as the body touching the position.
        """
        node_id = self._last_operation.get(key)
        return node_id is not None and not isinstance(
            self._nodes[node_id], RequirementNode
        )

    def record_action_trigger(
        self,
        callee: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        requirements: Iterable[ast.PositionReference],
        caller_requirement_positions: Iterable[ast.PositionReference],
    ) -> int:
        """Record that this action triggers ``callee``, returning the firing operation's id.

        The firing operation is the one that filled ``acting_on_position`` (a trigger position
        for an action, or the action being operated on by a constructor/destructor).

        ``caller_requirement_positions`` are ``requirements`` already expressed
        from the caller's perspective (``requirement.in_caller(callee)``), in the
        same order.
        """
        acting_on_position_key = acting_on_position.canonical_chained_name_tuple
        firing_node_id = self._last_operation[acting_on_position_key]
        firing_node = self._nodes[firing_node_id]
        callee_action = callee.get_last_action()
        callee_action_key = callee.canonical_chained_name_tuple
        satisfiers: dict[tuple[str, ...], int] = {}
        # Trigger positions are direct children of the callee chain.
        acting_on_is_trigger_position = (
            len(acting_on_position_key) == len(callee_action_key) + 1
            and acting_on_position_key[: len(callee_action_key)] == callee_action_key
        )
        if acting_on_is_trigger_position:
            # If we see that we are filling a trigger position, we add the trigger
            # position as a requirement node (becasue it doesn't show up in the
            # normal requirements).
            trigger_position_key = acting_on_position_key[len(callee_action_key) :]
        else:
            # We are firing a constructor or destructor, and this node needs
            # to be in the graph in order for it to fire.
            trigger_position_key = ()
        firing_node.satisfies.append(
            RequirementSatisfaction(callee_action, trigger_position_key, firing_node_id)
        )
        satisfiers[trigger_position_key] = firing_node_id
        for requirement, caller_position in zip(
            requirements, caller_requirement_positions, strict=True
        ):
            in_callee_key = caller_position.canonical_chained_name_tuple
            requirement_key = requirement.canonical_chained_name_tuple
            satisfier = self._requirement_satisfier(in_callee_key)
            if satisfier is not None:
                self._nodes[satisfier].satisfies.append(
                    RequirementSatisfaction(
                        callee_action, requirement_key, firing_node_id
                    )
                )
                satisfiers[requirement_key] = satisfier
        self._triggers.append(ActionTrigger(callee_action, firing_node_id, satisfiers))
        return firing_node_id

    @property
    def triggers(self) -> Sequence[ActionTrigger]:
        """Every action this action triggers, in the order it triggers them."""
        return self._triggers

    def _requirement_satisfier(self, in_callee_key: tuple[str, ...]) -> int | None:
        """Return the operation on ``in_callee_key`` that satisfies a callee's requirement, or None."""
        if in_callee_key not in self._last_operation:
            # We need to materialize RequirementNodes to propagate to the caller.
            _ = self._most_recent_ancestor_chain_operation(in_callee_key)
        return self._last_operation.get(in_callee_key)

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
        if not dependencies:
            # An operation with nothing else to wait on still happens only
            # because this action triggered, so it waits on the trigger
            # requirement like any other requirement.
            return [self._trigger_position_requirement_node_id]
        return sorted(dependencies)

    def _most_recent_ancestor_chain_operation(
        self, position: tuple[str, ...]
    ) -> int | None:
        """Return the most recent operation on ``position``'s ancestor chain, materializing requirements as needed."""
        ancestor: int | None = None
        for length in range(1, len(position) + 1):
            key = position[:length]
            existing = self._last_operation.get(key)
            if existing is not None:
                if ancestor is None or existing > ancestor:
                    ancestor = existing
                continue
            materialized_id = self._maybe_materialize_requirement_node(key, ancestor)
            if materialized_id is not None:
                ancestor = materialized_id
        return ancestor

    def _maybe_materialize_requirement_node(
        self, key: tuple[str, ...], ancestor: int | None
    ) -> int | None:
        """Materialize a RequirementNode standing in for the caller op on ``key``, or None."""
        # The position isn't one of our inferred requirements, no need to worry abut it.
        requirement = self._requirements.get(key)
        if requirement is None:
            return None
        # There is an ancestor operation, and isn't a requirement node (meaning we are already
        # past requirements on this position).
        if ancestor is not None and not isinstance(
            self._nodes[ancestor], RequirementNode
        ):
            return None
        return self._add_requirement_node(key, ancestor, requirement.required_state)

    def _add_requirement_node(
        self,
        key: tuple[str, ...],
        ancestor: int | None,
        required_state: action_contract.PositionOccupancyState,
    ) -> int:
        """Add a RequirementNode standing in for the caller op on ``key``, returning its id."""
        node_id = len(self._nodes)
        node = RequirementNode(
            node_id=node_id,
            required_state=required_state,
            requirement_position=key,
            depends_on=[ancestor] if ancestor is not None else [],
        )
        self._nodes.append(node)
        # A later body operation on the position must still chain onto this node,
        # but an existing operation there stays the most recent one.
        _ = self._last_operation.setdefault(key, node_id)
        self._requirement_nodes[key] = node
        return node_id

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
        callee_chain: tuple[str, ...],
        guaranteed_keys: Iterable[tuple[str, ...]],
    ):
        """Record the positions the trigger of ``callee_chain`` guarantees, as nodes hanging off it.

        Each key in ``guaranteed_keys`` is a contracted position's absolute key.
        That position's last operation becomes a new guarantee node, so caller
        operations that read it depend on the callee's final operation on it
        rather than on the trigger operation itself. The node names the position
        as the callee's own graph names it, including a position the callee in
        turn took from an action it triggered.
        """
        for absolute_key in guaranteed_keys:
            node_id = len(self._nodes)
            self._nodes.append(
                GuaranteeNode(
                    node_id=node_id,
                    action=callee_chain[-1],
                    guaranteed_position=ast.chain_in_callee(callee_chain, absolute_key),
                    depends_on=[trigger_node_id],
                )
            )
            self._last_operation[absolute_key] = node_id
