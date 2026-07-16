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

type PrecedingChildOperations = Iterable[tuple[tuple[str, ...], int]]


def _shares_path(one: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """Return whether either child position is a prefix of the other."""
    shared_depth = min(len(one), len(other))
    return one[:shared_depth] == other[:shared_depth]


@dataclass(frozen=True, slots=True)
class ChildOperation:
    """A caller operation on a transitive child position of a required position."""

    # The child position relative to the required position.
    child_position: tuple[str, ...]
    # The operation node in the caller's graph.
    node_id: int


@dataclass(frozen=True, slots=True)
class ParticleChildOperations:
    """Immutable operations on the child positions of one particle.

    Each value is a construction-time snapshot of operations that may become
    predecessors of a later operation that empties the particle. The operations
    have no guaranteed order.
    """

    operations: tuple[ChildOperation, ...] = ()

    @classmethod
    def from_preceding_operations(
        cls, preceding_operations: PrecedingChildOperations
    ) -> ParticleChildOperations:
        """Create a snapshot from preceding operations on child positions."""
        operations: list[ChildOperation] = []
        operation_positions: set[tuple[str, ...]] = set()
        operation_position_prefixes: set[tuple[str, ...]] = set()
        # The caller passes in every child operation that precedes this one.
        # We need to calculate the ones that are actually relevant for future
        # emptying operations.
        #
        # We find the deepest child unless a parent was operated on more recently.
        for child_position, node_id in sorted(
            preceding_operations, key=lambda operation: operation[1], reverse=True
        ):
            if (
                child_position in operation_positions
                or child_position in operation_position_prefixes
            ):
                continue
            has_operation_on_parent_position = any(
                child_position[:depth] in operation_positions
                for depth in range(1, len(child_position))
            )
            if has_operation_on_parent_position:
                continue
            operations.append(ChildOperation(child_position, node_id))
            operation_positions.add(child_position)
            operation_position_prefixes.update(
                child_position[:depth] for depth in range(1, len(child_position))
            )
        return cls(tuple(operations))

    def operations_not_on_same_paths_as(
        self, relative_positions: frozenset[tuple[str, ...]]
    ) -> list[ChildOperation]:
        """Return surviving operations independent of the supplied paths."""
        operations: list[ChildOperation] = []
        for operation in self.operations:
            shares_dependency_path = any(
                _shares_path(operation.child_position, dependency)
                for dependency in relative_positions
            )
            if not shares_dependency_path:
                operations.append(operation)
        return operations

    def all_precede(self, node_id: int) -> bool:
        """Return whether every operation precedes ``node_id``."""
        return not self.operations or self.operations[0].node_id < node_id

    def child_position_set(self) -> frozenset[tuple[str, ...]]:
        """Return the relative child positions with preceding operations."""
        return frozenset(operation.child_position for operation in self.operations)


@dataclass(frozen=True, slots=True)
class RequirementBinding:
    """The caller dependencies that satisfy one requirement of a triggered callee."""

    # The operation or RequirementNode that put the position in its required
    # state from the caller's perspective.
    node_id: int
    child_operations: ParticleChildOperations
    # node_id identifies what put the position in its required state. This
    # optional node identifies the additional dependencies needed if the callee
    # empties the required particle.
    requirement_children_node: RequirementChildrenNode | None


@dataclass(frozen=True, slots=True)
class ActionTrigger:
    """One triggering of a callee, and what satisfies each requirement of the callee.

    Recorded from the caller's side, at the moment it triggers, because only the
    caller knows what it did to the positions the callee names.
    """

    # The action reference this triggering fires, from the caller's perspective.
    callee: ast.ActionReference
    # The operation that triggered the callee.
    trigger_node_id: int
    # What satisfies each requirement of the callee, by the callee's own key for
    # that requirement.
    bindings: dict[tuple[str, ...], RequirementBinding]

    @property
    def callee_action_name(self) -> ast.GlobalTypedNameReference:
        """Return the final action in the reference."""
        return self.callee.get_last_action()

    @property
    def action_chain(self) -> tuple[str, ...]:
        """Return the caller's chained name for the action."""
        return self.callee.canonical_chained_name_tuple


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
    """A position a triggered action guarantees, which the callee itself operates on.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that fired the trigger; codegen resolves
    this node to the callee's last operation on ``guaranteed_position`` when it
    splices ``action`` in at that trigger. Caller operations that read the
    position depend on this node with ordinary edges.
    """

    # The triggering of the action that guarantees the position.
    trigger: ActionTrigger
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
    # This action's own key for the caller-controlled contracted position. Two
    # requirement nodes on different positions are otherwise identical, so it is
    # left out of equality to keep the tests' expected nodes readable.
    requirement_position: tuple[str, ...] = field(default=(), compare=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementChildrenNode(OperationNode):
    """The caller contribution required when this action empties a required particle.

    ``depends_on_child_operations`` identifies, by relative child position, the
    child operations that are already ordinary dependencies of the operation
    emptying the required particle.
    """

    requirement_position: tuple[str, ...]
    depends_on_child_operations: frozenset[tuple[str, ...]]


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
        # Every triggering this action performs, in the order it performs them.
        # One operation can fire more than one (creating a particle fires every
        # constructor it has).
        self._triggers: list[ActionTrigger] = []
        # The last triggering that used each RequirementNode to satisfy one of
        # its requirements. Guarantee resolution follows this reverse binding
        # when an action passes along a guarantee without operating on its
        # position itself.
        self._last_trigger_by_requirement_node_id: dict[int, ActionTrigger] = {}
        # Every action gets an occupied requirement on the position that triggers
        # it. This simplifies splicing together graphs, because the triggering
        # always has a requirement to map its firing operation to. A constructor or
        # destructor gets a RequirementNode with an empty key as a symbolic stand-in
        # for "the action got triggered."
        trigger_position_key = (
            trigger_position.canonical_chained_name_tuple
            if trigger_position is not None
            else ()
        )
        self._trigger_position_requirement_node_id: int = self._add_requirement_node(
            trigger_position_key,
            ancestor=None,
            required_state=action_contract.PositionOccupancyState.OCCUPIED,
        )

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order; a node's id is its index here."""
        return self._nodes

    def last_operation_on_position(self, key: tuple[str, ...]) -> int:
        """Return the last operation this action performed on the position at ``key``."""
        return self._last_operation[key]

    def _last_operation_affecting_position(self, key: tuple[str, ...]) -> int | None:
        """Return the last operation that put the position at ``key`` in the state it is in, if any.

        This is either the last direct operation on the position, or the
        last move that put the parent particle into _its_ position.

        If there are no operations this action did that affected the named
        position in nay way, returns None.
        """
        operation = self._last_operation.get(key)
        if operation is not None:
            return operation
        ancestor = self._most_recent_existing_ancestor_operation(key)
        if ancestor is not None and isinstance(self._nodes[ancestor], MoveNode):
            return ancestor
        return None

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
        requirements: Sequence[ast.PositionReference],
        caller_requirement_positions: Sequence[ast.PositionReference],
        *,
        acting_on_preceding_child_operations: PrecedingChildOperations,
        required_preceding_child_operations: Iterable[PrecedingChildOperations],
    ) -> ActionTrigger:
        """Record that this action triggers ``callee``, returning that triggering.

        The firing operation is the one that filled ``acting_on_position`` (a trigger position
        for an action, or the action being operated on by a constructor/destructor).

        ``caller_requirement_positions`` are ``requirements`` already expressed
        from the caller's perspective (``requirement.in_caller(callee)``), in the
        same order. The child-operation arguments identify operations responsible
        for the current state of the particles' child positions.
        """
        acting_on_position_key = acting_on_position.canonical_chained_name_tuple
        firing_node_id = self._last_operation[acting_on_position_key]
        callee_action_key = callee.canonical_chained_name_tuple
        bindings: dict[tuple[str, ...], RequirementBinding] = {}
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
        bindings[trigger_position_key] = self._requirement_binding(
            acting_on_position_key,
            ParticleChildOperations.from_preceding_operations(
                acting_on_preceding_child_operations
            ),
            firing_node_id,
        )
        for requirement, caller_position, preceding_child_operations in zip(
            requirements,
            caller_requirement_positions,
            required_preceding_child_operations,
            strict=True,
        ):
            caller_position_key = caller_position.canonical_chained_name_tuple
            requirement_key = requirement.canonical_chained_name_tuple
            binding_node_id = self._requirement_binding_node_id(caller_position_key)
            if binding_node_id is not None:
                bindings[requirement_key] = self._requirement_binding(
                    caller_position_key,
                    ParticleChildOperations.from_preceding_operations(
                        preceding_child_operations
                    ),
                    binding_node_id,
                )
        trigger = ActionTrigger(callee, firing_node_id, bindings)
        self._triggers.append(trigger)
        for binding in bindings.values():
            binding_node = self._nodes[binding.node_id]
            if isinstance(binding_node, RequirementNode):
                self._last_trigger_by_requirement_node_id[binding.node_id] = trigger
        return trigger

    def _requirement_binding(
        self,
        position: tuple[str, ...],
        child_operations: ParticleChildOperations,
        node_id: int,
    ) -> RequirementBinding:
        """Return the caller dependencies that satisfy a callee requirement."""
        position_node = self._nodes[node_id]
        # A move that brought the whole particle here already depends on every
        # older child operation, so retaining them would add redundant edges.
        if isinstance(position_node, MoveNode) and child_operations.all_precede(
            node_id
        ):
            child_operations = ParticleChildOperations()
        requirement_children_node: RequirementChildrenNode | None = None
        if (
            isinstance(position_node, RequirementNode)
            and position_node.requirement_position == position
            and position_node.required_state
            is action_contract.PositionOccupancyState.OCCUPIED
        ):
            requirement_children_node = self._add_requirement_children_node(
                position,
                child_operations.child_position_set(),
            )
        return RequirementBinding(
            node_id,
            child_operations,
            requirement_children_node,
        )

    @property
    def triggers(self) -> Sequence[ActionTrigger]:
        """Every action this action triggers, in the order it triggers them."""
        return self._triggers

    def last_trigger_using_requirement(self, requirement_node_id: int) -> ActionTrigger:
        """Return the last triggering that used ``requirement_node_id`` to satisfy a requirement."""
        return self._last_trigger_by_requirement_node_id[requirement_node_id]

    def _requirement_binding_node_id(
        self, caller_position_key: tuple[str, ...]
    ) -> int | None:
        """Return the operation on ``caller_position_key`` that satisfies a callee requirement, or None."""
        if caller_position_key not in self._last_operation:
            # We need to materialize RequirementNodes to propagate to the caller.
            _ = self._most_recent_ancestor_chain_operation(caller_position_key)
        # A move of an ancestor position carried this position along with it, so
        # that move is what put it in the state the callee needs, even though
        # nothing operated on the position itself.
        return self._last_operation_affecting_position(caller_position_key)

    def _fill_dependencies(self, position: tuple[str, ...]) -> set[int]:
        """Return dependencies required before filling ``position``."""
        dependencies: set[int] = set()
        # Filling a position waits on the most recent operation on that position
        # and its parents, so the parent is present to hold it.
        filled_ancestor = self._most_recent_ancestor_chain_operation(position)
        if filled_ancestor is not None:
            dependencies.add(filled_ancestor)
        return dependencies

    def _empty_dependencies(
        self,
        position: tuple[str, ...],
        child_operations: ParticleChildOperations,
    ) -> set[int]:
        """Return dependencies required before emptying ``position``."""
        # Emptying a position waits on the most recent operation in each touched
        # child position (minus a shallower one a deeper touched position has
        # already superseded), and on the emptied position's own chain only when
        # that is more recent than every one of those child operations; otherwise
        # a child already reaches it.
        dependencies: set[int] = set()
        emptied_ancestor = self._most_recent_ancestor_chain_operation(position)
        if emptied_ancestor is not None:
            node = self._nodes[emptied_ancestor]
            if (
                isinstance(node, RequirementNode)
                and node.requirement_position == position
            ):
                requirement_children_node = self._add_requirement_children_node(
                    position, child_operations.child_position_set()
                )
                dependencies.add(requirement_children_node.node_id)
            elif child_operations.all_precede(emptied_ancestor):
                child_operations = ParticleChildOperations()
                dependencies.add(emptied_ancestor)
        dependencies.update(
            operation.node_id for operation in child_operations.operations
        )
        return dependencies

    def _operation_dependencies(self, dependencies: set[int]) -> list[int]:
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
        return node_id

    def _add_requirement_children_node(
        self,
        requirement_position: tuple[str, ...],
        depends_on_child_operations: frozenset[tuple[str, ...]],
    ) -> RequirementChildrenNode:
        """Add and return the caller contribution for emptying a required particle."""
        node_id = len(self._nodes)
        node = RequirementChildrenNode(
            node_id=node_id,
            # Its dependencies are resolved through a RequirementBinding.
            depends_on=[],
            requirement_position=requirement_position,
            depends_on_child_operations=depends_on_child_operations,
        )
        self._nodes.append(node)
        return node

    def record_create(self, target: ast.PositionReference) -> int:
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(self._fill_dependencies(key))
        node_id = len(self._nodes)
        self._nodes.append(
            CreateNode(node_id=node_id, target=target, depends_on=depends_on)
        )
        self._last_operation[key] = node_id
        return node_id

    def record_move(
        self,
        source: ast.PositionReference,
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> int:
        """Record a body move from ``source`` to ``target``."""
        child_operations = ParticleChildOperations.from_preceding_operations(
            preceding_child_operations
        )
        source_key = source.canonical_chained_name_tuple
        target_key = target.canonical_chained_name_tuple
        dependencies = self._fill_dependencies(target_key)
        dependencies.update(self._empty_dependencies(source_key, child_operations))
        depends_on = self._operation_dependencies(dependencies)
        node_id = len(self._nodes)
        self._nodes.append(
            MoveNode(
                node_id=node_id, target=target, source=source, depends_on=depends_on
            )
        )
        self._last_operation[source_key] = node_id
        self._last_operation[target_key] = node_id
        return node_id

    def record_destroy(
        self,
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> int:
        """Record a destroy of ``target``.

        The single node covers the whole cascade, including the child positions
        it removes and the positions its fired destructors read.
        """
        child_operations = ParticleChildOperations.from_preceding_operations(
            preceding_child_operations
        )
        key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(
            self._empty_dependencies(key, child_operations)
        )
        node_id = len(self._nodes)
        self._nodes.append(
            DestroyNode(node_id=node_id, target=target, depends_on=depends_on)
        )
        self._last_operation[key] = node_id
        return node_id

    def record_guarantees(
        self,
        trigger: ActionTrigger,
        callee_chain: tuple[str, ...],
        guaranteed_keys: Iterable[tuple[str, ...]],
    ) -> dict[tuple[str, ...], int]:
        """Record the positions ``trigger`` guarantees, as nodes hanging off it.

        Each key in ``guaranteed_keys`` is a contracted position's absolute key.
        That position's last operation becomes a new guarantee node, so caller
        operations that read it depend on the callee's final operation on it
        rather than on the trigger operation itself. The node names the position
        as the callee's own graph names it, including a position the callee in
        turn took from an action it triggered.
        """
        node_ids: dict[tuple[str, ...], int] = {}
        for absolute_key in guaranteed_keys:
            node_id = len(self._nodes)
            self._nodes.append(
                GuaranteeNode(
                    node_id=node_id,
                    trigger=trigger,
                    guaranteed_position=ast.chain_in_callee(callee_chain, absolute_key),
                    depends_on=[trigger.trigger_node_id],
                )
            )
            self._last_operation[absolute_key] = node_id
            node_ids[absolute_key] = node_id
        return node_ids
