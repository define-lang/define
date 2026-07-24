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

In general, operation graphs are designed such that they are the only thing
that codegen should need in order to generate code for all actions.

Operation graphs are only expected to be valid for valid Define code. None of
the code in this module needs to deal with invalid Define code, as such graphs
will never be passed to codegen. The only "invalid code" situation we might need
to care about is anything that would cause an infinite loop in this code, but
generally the validator should never even reach the operation graph's methods
in any such situation.
"""

from __future__ import annotations

import collections
import typing
from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import action_contract

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

type PrecedingChildOperationNode = PositionOperationNode | GuaranteeNode
type LastOperationNode = PrecedingChildOperationNode | RequirementNode
type ActionParentOperationNode = ActionParentLastOperationNode | LastOperationNode
type PrecedingChildOperations = Iterable[
    tuple[tuple[str, ...], PrecedingChildOperationNode]
]


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
    operation: PrecedingChildOperationNode


@dataclass(frozen=True, slots=True)
class ParticleChildOperations:
    """Immutable operations on the child positions of one particle.

    Each value is a construction-time snapshot of operations that may become
    predecessors of a later operation that empties the particle. Operations are
    ordered from most recent to least recent.
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
        for child_position, operation in sorted(
            preceding_operations,
            key=lambda item: item[1].node_id,
            reverse=True,
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
            operations.append(ChildOperation(child_position, operation))
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

    def all_precede(self, operation: MoveNode) -> bool:
        """Return whether every child operation precedes ``operation``."""
        return (
            not self.operations
            or self.operations[0].operation.node_id < operation.node_id
        )

    def child_position_set(self) -> frozenset[tuple[str, ...]]:
        """Return the relative child positions with preceding operations."""
        return frozenset(operation.child_position for operation in self.operations)


@dataclass(frozen=True, slots=True)
class CallerEmptyRuleDependencies:
    """Information needed to apply the Empty Rule through caller bindings.

    ``requirement_position`` contains the particle being emptied.
    ``dependency_child_positions`` are relative to that position and identify
    operations that are already dependencies. ``dependency_requirements`` must
    be combined with those operations.
    """

    requirement_position: tuple[str, ...]
    dependency_child_positions: frozenset[tuple[str, ...]]
    dependency_requirements: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class CallerEmptyRuleSubstitution:
    """The result of substituting caller bindings into CallerEmptyRuleDependencies."""

    dependency_nodes: tuple[LastOperationNode, ...]
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies | None


@dataclass(frozen=True, slots=True)
class RequirementBinding:
    """The caller dependencies that satisfy one requirement of a triggered callee."""

    # The operation or RequirementNode that put the position in its required
    # state from the caller's perspective.
    operation: LastOperationNode
    child_operations: ParticleChildOperations


@dataclass(frozen=True, slots=True)
class ActionTrigger:
    """One triggering of a callee, and what satisfies each requirement of the callee.

    Recorded from the caller's side, at the moment it triggers, because only the
    caller knows what it did to the positions the callee names.
    """

    # The action reference this triggering fires, from the caller's perspective.
    callee: ast.ActionReference
    # The operation that triggered the callee.
    trigger_operation: LastOperationNode
    # What satisfies each requirement of the callee, by the callee's own key for
    # that requirement.
    bindings: dict[tuple[str, ...], RequirementBinding]
    # The last operation on the callee action's parent position or one of that
    # position's transitive parent positions.
    action_parent_last_operation: ActionParentOperationNode = field(kw_only=True)

    @property
    def callee_action_name(self) -> ast.GlobalTypedNameReference:
        """Return the final action in the reference."""
        return self.callee.get_last_action()

    @property
    def action_chain(self) -> tuple[str, ...]:
        """Return the caller's chained name for the action."""
        return self.callee.canonical_chained_name_tuple


class GuaranteedPositions:
    """Guaranteed positions expressed from the caller's perspective."""

    def __init__(
        self,
        parent_chain: tuple[str, ...],
        guarantees: Iterable[tuple[tuple[str, ...], action_contract.PositionGuarantee]],
    ):
        """Express every guarantee's operation positions from the caller's perspective."""
        self._parent_chain: tuple[str, ...] = parent_chain
        self._guarantees: Iterable[
            tuple[tuple[str, ...], action_contract.PositionGuarantee]
        ] = guarantees

    def items(
        self,
    ) -> Iterable[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]]:
        """Iterate over each absolute key and its operation positions."""
        for absolute_key, guarantee in self._guarantees:
            yield (
                absolute_key,
                tuple(
                    ast.chain_in_caller(self._parent_chain, position)
                    for position in guarantee.operation_positions
                ),
            )


# A node_id is unique only within one graph, so nodes use identity equality and
# hashing when they appear in sets and mappings. Every dataclass subclass must
# repeat eq=False because dataclass decorator options are not inherited.
@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class OperationNode:
    """One operation in an action's dependency graph."""

    node_id: int
    # The operations this node directly depends on (the operations that must
    # complete before it).
    depends_on: tuple[OperationNode, ...]

    @property
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ActionParentLastOperationNode(OperationNode):
    """The caller's last operation on this action's parent position or its transitive parents."""

    depends_on: tuple[()]


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class PositionOperationNode(OperationNode):
    """An operation the body performs on a written position."""

    # The position reference as written (the statement target).
    target: ast.PositionReference

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return (self.target.canonical_chained_name_tuple,)


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CreateNode(PositionOperationNode):
    """A body create in ``target``."""


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class MoveNode(PositionOperationNode):
    """A body move of a particle from ``source`` to ``target``."""

    source: ast.PositionReference

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return (
            self.source.canonical_chained_name_tuple,
            self.target.canonical_chained_name_tuple,
        )


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class DestroyNode(PositionOperationNode):
    """A destroy of ``target``.

    A destroy statement or an auto-destruction at block end; one node covers the
    whole cascade.
    """


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class GuaranteeNode(OperationNode):
    """A position a triggered action guarantees, which the callee itself operates on.

    This stands in for an operation whose details live in the callee's own graph.
    ``depends_on`` holds the operation that fired the trigger; codegen resolves
    this node to the callee's last operation on ``guaranteed_position`` when it
    splices ``action`` in at that trigger. Caller operations that read the
    position depend on this node with ordinary edges.
    """

    depends_on: tuple[LastOperationNode, ...]
    # The triggering of the action that guarantees the position.
    trigger: ActionTrigger
    # The guaranteed position, by the callee's own key for it.
    guaranteed_position: tuple[str, ...]
    # Every caller position operated on by the guaranteed Particle Operation.
    operation_positions: tuple[tuple[str, ...], ...]

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return self.operation_positions


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class RequirementNode(OperationNode):
    """A caller-controlled contracted position an operation needs in a given state.

    This stands in for the caller operation that satisfies an inferred requirement.
    The renderer/codegen resolves it to the caller op that most recently operated
    on ``requirement_position`` before the trigger. A position can be empty
    without any operation emptying it, so an empty requirement can have no such
    caller op at all, which is why the required state is recorded here.
    """

    depends_on: tuple[ActionParentLastOperationNode | RequirementNode, ...]
    # The state this action needs the position to be in.
    required_state: action_contract.PositionOccupancyState
    # This action's own key for the caller-controlled contracted position.
    requirement_position: tuple[str, ...] = field(default=(), compare=False)

    @property
    @typing.override
    def operated_positions(self) -> tuple[tuple[str, ...], ...]:
        """Every position operated on by this node."""
        return (self.requirement_position,)


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class CallerEmptyRuleDependenciesNode(OperationNode):
    """Caller dependencies needed when an action empties a required particle.

    ``caller_empty_rule_dependencies`` preserves the complete Empty Rule dependency set
    while caller requirement bindings are substituted.
    """

    depends_on: tuple[()]
    caller_empty_rule_dependencies: CallerEmptyRuleDependencies


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
        # A position's canonical chained name -> the last operation on it,
        # for every position the body touches.
        # cProfile makes ancestor lookup through this flat mapping look like a
        # performance problem because dense action call graphs perform millions
        # of prefix checks. Unprofiled experiments in July 2026 showed that the
        # lookup is not a meaningful share of whole-compiler CPU time:
        # - A prefix trie intended to avoid tuple slicing made dense action call
        #   graphs 21-25% slower and a deeply chained position-operation workload
        #   17% slower. It also used enough memory to kill the largest test.
        # - A compact index for requirements without RequirementNodes appeared
        #   successful under cProfile: it removed millions of prefix checks and
        #   made the lookup routines 21-27% faster. It failed to produce a real
        #   compiler improvement, however. Alternating unprofiled compilations
        #   differed by only 0.6%, within normal run-to-run variation, so the
        #   prototype was rejected.
        # Do not retry either representation without evidence that workload
        # shape or this algorithm has materially changed; the number of semantic
        # effects constructed and propagated dominates these lookup costs.
        self._last_operation: dict[tuple[str, ...], LastOperationNode] = {}
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
        self._last_trigger_by_requirement_node: dict[
            RequirementNode, ActionTrigger
        ] = {}
        # Every local position has the position of the particle this action is
        # assigned to as a transitive parent from the caller's perspective.
        self._action_parent_last_operation: ActionParentLastOperationNode = (
            ActionParentLastOperationNode(
                node_id=len(self._nodes),
                depends_on=(),
            )
        )
        self._nodes.append(self._action_parent_last_operation)
        self._trigger_position_key: tuple[str, ...] = (
            trigger_position.canonical_chained_name_tuple
            if trigger_position is not None
            else ()
        )
        self._guaranteed_positions_by_operation: dict[
            PositionOperationNode, tuple[tuple[str, ...], ...]
        ] = {}

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order."""
        return self._nodes

    @property
    def guaranteed_positions_by_operation(
        self,
    ) -> dict[PositionOperationNode, tuple[tuple[str, ...], ...]]:
        """Return locally published guarantees grouped by Particle Operation."""
        return self._guaranteed_positions_by_operation

    def last_operation_on_position(self, key: tuple[str, ...]) -> LastOperationNode:
        """Return the last operation this action performed on the position at ``key``."""
        return self._last_operation[key]

    def body_touched_key(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly this key.

        A materialized RequirementNode stands in for a caller operation, not a
        body operation, so it does not count as the body touching the position.
        """
        node = self._last_operation.get(key)
        return node is not None and not isinstance(node, RequirementNode)

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
        firing_operation = self._last_operation[acting_on_position_key]
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
            ParticleChildOperations.from_preceding_operations(
                acting_on_preceding_child_operations
            ),
            firing_operation,
        )
        for requirement, caller_position, preceding_child_operations in zip(
            requirements,
            caller_requirement_positions,
            required_preceding_child_operations,
            strict=True,
        ):
            caller_position_key = caller_position.canonical_chained_name_tuple
            requirement_key = requirement.canonical_chained_name_tuple
            binding_operation = self._requirement_binding_operation(caller_position_key)
            if binding_operation is not None:
                bindings[requirement_key] = self._requirement_binding(
                    ParticleChildOperations.from_preceding_operations(
                        preceding_child_operations
                    ),
                    binding_operation,
                )
        action_parent_position = callee.parent_position()
        if action_parent_position is None:
            # The action is an implied action--it's assigned to the
            # same parent as we are.
            action_parent_last_operation = self._action_parent_last_operation
        else:
            action_parent_last_operation = typing.cast(
                "LastOperationNode",
                self._most_recent_ancestor_chain_operation(
                    action_parent_position.canonical_chained_name_tuple
                ),
            )
        trigger = ActionTrigger(
            callee=callee,
            trigger_operation=firing_operation,
            bindings=bindings,
            action_parent_last_operation=action_parent_last_operation,
        )
        self._triggers.append(trigger)
        for binding in bindings.values():
            if isinstance(binding.operation, RequirementNode):
                self._last_trigger_by_requirement_node[binding.operation] = trigger
        return trigger

    def _requirement_binding(
        self,
        child_operations: ParticleChildOperations,
        operation: LastOperationNode,
    ) -> RequirementBinding:
        """Return the caller dependencies that satisfy a callee requirement."""
        # A move that brought the whole particle here already depends on every
        # older child operation, so retaining them would add redundant edges.
        if isinstance(operation, MoveNode) and child_operations.all_precede(operation):
            child_operations = ParticleChildOperations()
        return RequirementBinding(operation, child_operations)

    @property
    def triggers(self) -> Sequence[ActionTrigger]:
        """Every action this action triggers, in the order it triggers them."""
        return self._triggers

    def last_trigger_using_requirement(
        self, requirement_node: RequirementNode
    ) -> ActionTrigger:
        """Return the last triggering that used ``requirement_node``."""
        return self._last_trigger_by_requirement_node[requirement_node]

    def _requirement_binding_operation(
        self, caller_position_key: tuple[str, ...]
    ) -> LastOperationNode | None:
        """Return the operation on ``caller_position_key`` that satisfies a callee requirement, or None."""
        operation = self._last_operation.get(caller_position_key)
        if operation is not None:
            return operation
        # We need to materialize RequirementNodes to propagate to the caller.
        ancestor_operation = self._most_recent_ancestor_chain_operation(
            caller_position_key
        )
        operation = self._last_operation.get(caller_position_key)
        if operation is not None:
            return operation
        # A move of a parent position also put this position in its current state.
        if isinstance(ancestor_operation, MoveNode):
            return ancestor_operation
        return None

    def _operation_dependencies(
        self,
        *,
        empty_position: tuple[str, ...] | None = None,
        fill_position: tuple[str, ...] | None = None,
        child_operations: ParticleChildOperations | None = None,
    ) -> tuple[OperationNode, ...]:
        """Return dependencies required before optionally emptying and filling positions."""
        if child_operations is None:
            child_operations = ParticleChildOperations()
        fill_dependency: LastOperationNode | None = None
        if fill_position is not None:
            # Filling a position waits on the most recent operation on that
            # position and its parent names, so the parent particle is present.
            fill_dependency = self._most_recent_ancestor_chain_operation(fill_position)

        if empty_position is not None:
            dependencies = self._empty_dependencies(
                empty_position, child_operations, fill_dependency
            )
            if dependencies:
                return dependencies
        elif fill_dependency is not None:
            return (fill_dependency,)
        return (self._action_parent_last_operation,)

    def _empty_dependencies(
        self,
        empty_position: tuple[str, ...],
        child_operations: ParticleChildOperations,
        fill_dependency: LastOperationNode | None,
    ) -> tuple[LastOperationNode | CallerEmptyRuleDependenciesNode, ...]:
        """Add the emptied particle's operations and apply the Empty Rule."""
        candidates: set[LastOperationNode | CallerEmptyRuleDependenciesNode] = set()
        emptied_ancestor = self._most_recent_ancestor_chain_operation(empty_position)
        if emptied_ancestor is not None:
            if (
                isinstance(emptied_ancestor, RequirementNode)
                and emptied_ancestor.requirement_position == empty_position
            ):
                dependency_requirements: tuple[tuple[str, ...], ...] = ()
                if fill_dependency is not None:
                    if isinstance(fill_dependency, RequirementNode):
                        # Allow the caller to apply the Move Rule.
                        dependency_requirements = (
                            fill_dependency.requirement_position,
                        )
                    else:
                        # We are going to apply the Move Rule here inside this action
                        # (during _reduce dependencies).
                        candidates.add(fill_dependency)
                caller_empty_rule_dependencies = self._add_caller_empty_rule_dependencies(
                    CallerEmptyRuleDependencies(
                        requirement_position=empty_position,
                        dependency_child_positions=child_operations.child_position_set(),
                        dependency_requirements=dependency_requirements,
                    )
                )
                candidates.add(caller_empty_rule_dependencies)
            else:
                candidates.add(emptied_ancestor)
                if fill_dependency is not None:
                    candidates.add(fill_dependency)
        elif fill_dependency is not None:
            candidates.add(fill_dependency)
        candidates.update(
            child_operation.operation for child_operation in child_operations.operations
        )
        return self._reduce_dependencies(candidates)

    def _reduce_dependencies[DependencyNodeT: OperationNode](
        self, candidates: set[DependencyNodeT]
    ) -> tuple[DependencyNodeT, ...]:
        """Apply the Empty Rule to candidate dependencies."""
        dependencies: list[DependencyNodeT] = []
        newer_positions: set[tuple[str, ...]] = set()
        newer_position_prefixes: set[tuple[str, ...]] = set()
        for node in sorted(
            candidates,
            key=lambda item: item.node_id,
            reverse=True,
        ):
            positions = node.operated_positions
            has_newer_related_operation = self._has_related_position(
                positions, newer_positions, newer_position_prefixes
            )
            if not has_newer_related_operation:
                dependencies.append(node)
            # An operation covered by a newer operation still covers every older
            # operation that shares one of its other positions. Keeping its
            # positions here preserves that ordering through chains of moves.
            for position in positions:
                newer_positions.add(position)
                newer_position_prefixes.update(
                    position[:depth] for depth in range(1, len(position))
                )
        dependencies.reverse()
        return tuple(dependencies)

    @staticmethod
    def _has_related_position(
        positions: tuple[tuple[str, ...], ...],
        other_positions: set[tuple[str, ...]],
        other_position_prefixes: set[tuple[str, ...]],
    ) -> bool:
        """Return whether any position shares a parent-child path with another position."""
        for position in positions:
            if position in other_positions or position in other_position_prefixes:
                return True
            for depth in range(1, len(position)):
                if position[:depth] in other_positions:
                    return True
        return False

    def _most_recent_ancestor_chain_operation(
        self, position: tuple[str, ...]
    ) -> LastOperationNode | None:
        """Return the most recent operation on ``position``'s ancestor chain, materializing requirements as needed."""
        ancestor: LastOperationNode | None = None
        for length in range(1, len(position) + 1):
            key = position[:length]
            existing = self._last_operation.get(key)
            if existing is not None:
                if ancestor is None or existing.node_id > ancestor.node_id:
                    ancestor = existing
                continue
            materialized = self._maybe_materialize_requirement_node(key, ancestor)
            if materialized is not None:
                ancestor = materialized
        return ancestor

    def _maybe_materialize_requirement_node(
        self, key: tuple[str, ...], ancestor: LastOperationNode | None
    ) -> RequirementNode | None:
        """Materialize a RequirementNode standing in for the caller op on ``key``, or None."""
        requirement = self._requirements.get(key)
        if requirement is not None:
            required_state = requirement.required_state
        elif key == self._trigger_position_key:
            required_state = action_contract.PositionOccupancyState.OCCUPIED
        else:
            # Not a position we have a requirement on.
            return None
        # There is an ancestor operation, and isn't a requirement node (meaning we are already
        # past requirements on this position).
        if ancestor is not None and not isinstance(ancestor, RequirementNode):
            return None
        return self._add_requirement_node(key, ancestor, required_state)

    def _add_requirement_node(
        self,
        key: tuple[str, ...],
        ancestor: RequirementNode | None,
        required_state: action_contract.PositionOccupancyState,
    ) -> RequirementNode:
        """Add a RequirementNode standing in for the caller operation on ``key``."""
        dependency = ancestor
        if dependency is None:
            dependency = self._action_parent_last_operation
        node = RequirementNode(
            node_id=len(self._nodes),
            required_state=required_state,
            requirement_position=key,
            depends_on=(dependency,),
        )
        self._nodes.append(node)
        # A later body operation on the position must still chain onto this node,
        # but an existing operation there stays the most recent one.
        _ = self._last_operation.setdefault(key, node)
        return node

    def _add_caller_empty_rule_dependencies(
        self, caller_empty_rule_dependencies: CallerEmptyRuleDependencies
    ) -> CallerEmptyRuleDependenciesNode:
        """Add and return the caller contribution for emptying a required particle."""
        node = CallerEmptyRuleDependenciesNode(
            node_id=len(self._nodes),
            depends_on=(),
            caller_empty_rule_dependencies=caller_empty_rule_dependencies,
        )
        self._nodes.append(node)
        return node

    def substitute_caller_empty_rule_dependencies(
        self,
        caller_empty_rule_dependencies: CallerEmptyRuleDependencies,
        bindings: Mapping[tuple[str, ...], RequirementBinding],
    ) -> CallerEmptyRuleSubstitution:
        """Substitute a callee's dependencies with operations from this caller."""
        callee_requirement_binding = bindings[
            caller_empty_rule_dependencies.requirement_position
        ]
        child_operations = (
            callee_requirement_binding.child_operations.operations_not_on_same_paths_as(
                caller_empty_rule_dependencies.dependency_child_positions
            )
        )
        candidates: set[LastOperationNode] = {
            child_operation.operation for child_operation in child_operations
        }
        for requirement in caller_empty_rule_dependencies.dependency_requirements:
            # The Fill Rule allows its dependency to come from a transitive parent position.
            # _first_requirement_binding therefore checks the position and
            # its parent-position prefixes until it finds the caller binding that supplies
            # the dependency.
            binding = self._first_requirement_binding(requirement, bindings)
            # Note: None means this is an EMPTY requirement that is satisfied by default
            # (there was no specific operation that emptied the position). The Fill Rule
            # created a separate requirement against the parent position, and so no binding
            # is necessary here.
            if binding is not None:
                candidates.add(binding.operation)

        requirement_position_in_caller = self._occupied_requirement_position(
            callee_requirement_binding
        )
        # The particle is not from our caller, so we don't have to propagate
        # Empty Rule child dependencies on it.
        if requirement_position_in_caller is None:
            if (
                not child_operations
                and not caller_empty_rule_dependencies.dependency_child_positions
            ):
                # callee_requirement_binding.operation is the operation on the emptied
                # position. When there are no later child-position operations, it
                # remains the required dependency per the Empty Rule.
                candidates.add(callee_requirement_binding.operation)
            return CallerEmptyRuleSubstitution(
                self._reduce_dependencies(candidates),
                None,
            )

        # If this action received the particle from its caller, some operations
        # required by the Empty Rule may belong to that caller and must be propagated.
        # Apply what we can of the Empty Rule now to this caller's operations before
        # propagating dependencies from this caller's occupied requirement to its caller.
        dependencies = self._reduce_dependencies(candidates)
        dependency_nodes: list[PrecedingChildOperationNode] = []
        dependency_requirements: list[tuple[str, ...]] = []
        seen_dependency_requirements: set[tuple[str, ...]] = set()
        dependency_child_positions = set(
            callee_requirement_binding.child_operations.child_position_set()
        )
        dependency_child_positions.update(
            caller_empty_rule_dependencies.dependency_child_positions
        )
        for node in dependencies:
            if isinstance(node, RequirementNode):
                requirement_position = node.requirement_position
                if requirement_position not in seen_dependency_requirements:
                    dependency_requirements.append(requirement_position)
                    seen_dependency_requirements.add(requirement_position)
                continue
            dependency_nodes.append(node)
            # This remains linear in the positions on the dependencies because
            # each position is examined once, without comparing dependencies.
            self._add_positions_relative_to_particle(
                dependency_child_positions,
                node,
                requirement_position_in_caller,
            )
        return CallerEmptyRuleSubstitution(
            tuple(dependency_nodes),
            CallerEmptyRuleDependencies(
                requirement_position=requirement_position_in_caller,
                dependency_child_positions=frozenset(dependency_child_positions),
                dependency_requirements=tuple(dependency_requirements),
            ),
        )

    def _occupied_requirement_position(
        self, binding: RequirementBinding
    ) -> tuple[str, ...] | None:
        """Return the occupied requirement position represented by ``binding``."""
        node = binding.operation
        if not isinstance(node, RequirementNode):
            return None
        if node.required_state is not action_contract.PositionOccupancyState.OCCUPIED:
            return None
        return node.requirement_position

    @staticmethod
    def _first_requirement_binding(
        requirement_position: tuple[str, ...],
        bindings: Mapping[tuple[str, ...], RequirementBinding],
    ) -> RequirementBinding | None:
        """Return the first supplied binding in a requirement's parent chain."""
        for depth in range(len(requirement_position), 0, -1):
            binding = bindings.get(requirement_position[:depth])
            if binding is not None:
                return binding
        return None

    def _add_positions_relative_to_particle(
        self,
        relative_positions: set[tuple[str, ...]],
        node: PrecedingChildOperationNode,
        particle_position: tuple[str, ...],
    ):
        """Add a node's transitive parent and child positions relative to ``particle_position``."""
        for position in node.operated_positions:
            shared_depth = min(len(position), len(particle_position))
            if position[:shared_depth] != particle_position[:shared_depth]:
                continue
            if len(position) <= len(particle_position):
                # This represents the position itself or one of its parents.
                relative_positions.add(())
            else:
                relative_positions.add(position[len(particle_position) :])

    def record_create(self, target: ast.PositionReference) -> CreateNode:
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(fill_position=key)
        node = CreateNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=depends_on,
        )
        self._nodes.append(node)
        self._last_operation[key] = node
        return node

    def record_move(
        self,
        source: ast.PositionReference,
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> MoveNode:
        """Record a body move from ``source`` to ``target``."""
        child_operations = ParticleChildOperations.from_preceding_operations(
            preceding_child_operations
        )
        source_key = source.canonical_chained_name_tuple
        target_key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(
            empty_position=source_key,
            fill_position=target_key,
            child_operations=child_operations,
        )
        node = MoveNode(
            node_id=len(self._nodes),
            target=target,
            source=source,
            depends_on=depends_on,
        )
        self._nodes.append(node)
        self._last_operation[source_key] = node
        self._last_operation[target_key] = node
        return node

    def record_destroy(
        self,
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> DestroyNode:
        """Record a destroy of ``target``.

        The single node covers the whole cascade, including the child positions
        it removes and the positions its fired destructors read.
        """
        child_operations = ParticleChildOperations.from_preceding_operations(
            preceding_child_operations
        )
        key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(
            empty_position=key,
            child_operations=child_operations,
        )
        node = DestroyNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=depends_on,
        )
        self._nodes.append(node)
        self._last_operation[key] = node
        return node

    def record_guarantees(
        self,
        trigger: ActionTrigger,
        callee_chain: tuple[str, ...],
        guaranteed_positions: GuaranteedPositions,
    ) -> dict[tuple[str, ...], GuaranteeNode]:
        """Record the positions ``trigger`` guarantees, as nodes hanging off it.

        Each key is a contracted position's absolute key. That position's last
        operation becomes a new guarantee node, so caller operations that read
        it depend on the callee's final operation on it rather than on the
        trigger operation itself. The node names the position as the callee's
        own graph names it, including a position the callee in turn took from an
        action it triggered.
        """
        # The per-guarantee node and its one-element dependency list look like
        # avoidable allocation costs because guarantees account for most nodes
        # in dense action call graphs. A July 2026 experiment shared one
        # dependency list among every GuaranteeNode produced by the same
        # triggering, eliminating over one million list allocations in the
        # largest profile. It failed to reduce compiler CPU: alternating
        # unprofiled runs averaged 8.013s before and 8.037s after, so the
        # prototype was rejected as a CPU optimization.
        nodes: dict[tuple[str, ...], GuaranteeNode] = {}
        for absolute_key, operation_positions in guaranteed_positions.items():
            node = GuaranteeNode(
                node_id=len(self._nodes),
                trigger=trigger,
                guaranteed_position=ast.chain_in_callee(callee_chain, absolute_key),
                depends_on=(trigger.trigger_operation,),
                operation_positions=operation_positions,
            )
            self._nodes.append(node)
            self._last_operation[absolute_key] = node
            nodes[absolute_key] = node
        return nodes

    def record_guaranteed_positions(self, positions: Iterable[tuple[str, ...]]):
        """Record guarantees published by this action's Particle Operations."""
        positions_by_operation: dict[PositionOperationNode, list[tuple[str, ...]]] = {}
        for position in positions:
            node = self._last_operation.get(position)
            if not isinstance(node, PositionOperationNode):
                continue
            positions_by_operation.setdefault(node, []).append(position)
        self._guaranteed_positions_by_operation = {
            operation: tuple(guaranteed_positions)
            for operation, guaranteed_positions in positions_by_operation.items()
        }


@dataclass(frozen=True, slots=True)
class _CalleeGuaranteeResolution:
    """A direct callee through which a guarantee resolves."""

    trigger: ActionTrigger
    callee_resolution: _GuaranteeResolution


type _GuaranteeResolution = PositionOperationNode | _CalleeGuaranteeResolution


@typing.final
class OperationGraphs(
    typed_name_dict.TypedNameDict[ast.GlobalTypedName, OperationGraph]
):
    """The operation dependency graphs of every validated action.

    Not thread-safe. Adding an operation graph mutates the inherited mapping
    (which itself is not thread-safe), and ``resolve_guarantee`` mutates an
    internal lazy guarantee-resolution cache.
    """

    def __init__(self):
        """Initialize an empty operation-graph collection."""
        super().__init__()
        self._guarantee_resolutions: collections.defaultdict[
            str, dict[tuple[str, ...], _GuaranteeResolution]
        ] = collections.defaultdict(dict)

    def resolve_guarantee(
        self, guarantee: GuaranteeNode
    ) -> tuple[list[ActionTrigger], PositionOperationNode]:
        """Resolve one guarantee to its Particle Operation through callee graphs."""
        resolution = self._resolve_guaranteed_position(
            guarantee.trigger.callee_action_name, guarantee.guaranteed_position
        )
        triggers = [guarantee.trigger]
        while isinstance(resolution, _CalleeGuaranteeResolution):
            triggers.append(resolution.trigger)
            resolution = resolution.callee_resolution
        return triggers, resolution

    def _resolve_guaranteed_position(
        self, action: ast.GlobalTypedName, position: tuple[str, ...]
    ) -> _GuaranteeResolution:
        unresolved: list[tuple[str, tuple[str, ...], ActionTrigger]] = []
        while True:
            action_name = action.full_typed_name
            action_resolutions = self._guarantee_resolutions[action_name]
            cached = action_resolutions.get(position)
            if cached is not None:
                resolution = cached
                break

            graph = self[action]
            node = graph.last_operation_on_position(position)
            match node:
                case PositionOperationNode():
                    resolution = node
                    action_resolutions[position] = resolution
                    break
                case GuaranteeNode():
                    trigger = node.trigger
                    next_position = node.guaranteed_position
                case RequirementNode():
                    trigger = graph.last_trigger_using_requirement(node)
                    next_position = ast.chain_in_callee(trigger.action_chain, position)
            unresolved.append((action_name, position, trigger))
            action = trigger.callee_action_name
            position = next_position

        for action_name, position, trigger in reversed(unresolved):
            resolution = _CalleeGuaranteeResolution(trigger, resolution)
            self._guarantee_resolutions[action_name][position] = resolution
        return resolution
