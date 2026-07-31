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
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_model,
)
from define.compiler.validator.reference_graph.operation_graph_model import (
    ActionParentLastOperationNode,
    ActionParentOperationNode,
    ActionTrigger,
    CallerChildPositionEmptyRuleDependencies,
    CallerEmptyRuleDependencies,
    CallerEmptyRuleDependenciesNode,
    CallerEmptyRuleSubstitution,
    CallerParticleEmptyRuleDependencies,
    ChildOperation,
    CreateNode,
    DestroyIfOccupiedNode,
    DestroyNode,
    GuaranteeNode,
    LastOperationNode,
    MoveNode,
    OperationNode,
    ParticleChildOperations,
    PositionOperationNode,
    PrecedingChildOperationNode,
    PrecedingChildOperations,
    RequirementBinding,
    RequirementNode,
)

# TODO: Update type consumers to import these directly from
# operation_graph_model, then remove these re-exports.
__all__ = [
    "ActionParentLastOperationNode",
    "ActionParentOperationNode",
    "ActionTrigger",
    "CallerChildPositionEmptyRuleDependencies",
    "CallerEmptyRuleDependencies",
    "CallerEmptyRuleDependenciesNode",
    "CallerEmptyRuleSubstitution",
    "CallerParticleEmptyRuleDependencies",
    "ChildOperation",
    "CreateNode",
    "DestroyIfOccupiedNode",
    "DestroyNode",
    "GuaranteeNode",
    "GuaranteePath",
    "LastOperationNode",
    "MoveNode",
    "OperationGraph",
    "OperationGraphs",
    "OperationNode",
    "ParticleChildOperations",
    "PositionOperationNode",
    "PrecedingChildOperationNode",
    "PrecedingChildOperations",
    "RequirementBinding",
    "RequirementNode",
]

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


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
        self.guaranteed_positions_by_operation: dict[
            PositionOperationNode, tuple[tuple[str, ...], ...]
        ] = {}

    @property
    def nodes(self) -> Sequence[OperationNode]:
        """Every node, in creation order."""
        return self._nodes

    def last_operation_on_position(
        self, key: tuple[str, ...]
    ) -> PrecedingChildOperationNode | RequirementNode:
        """Return the last operation recorded on exactly ``key``."""
        return self._last_operation[key]

    def last_operation_on_position_or_parents(
        self, key: tuple[str, ...]
    ) -> PrecedingChildOperationNode | RequirementNode:
        """Return the last operation on ``key`` or one of its parent names."""
        last_operation: LastOperationNode | None = None
        for length in range(len(key), 0, -1):
            operation = self._last_operation.get(key[:length])
            if operation is not None and (
                last_operation is None or operation.node_id > last_operation.node_id
            ):
                last_operation = operation
        if last_operation is None:
            raise KeyError(key)
        return last_operation

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
        firing_operation = typing.cast(
            "PositionOperationNode",
            self._last_operation[acting_on_position_key],
        )
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
        fill_position: tuple[str, ...],
        empty_position: tuple[str, ...] | None = None,
        child_operations: ParticleChildOperations | None = None,
    ) -> tuple[OperationNode, ...]:
        """Return dependencies required before optionally emptying and filling positions."""
        if child_operations is None:
            child_operations = ParticleChildOperations()
        # Filling a position waits on the most recent operation on that
        # position and its parent names, so the parent particle is present.
        fill_dependency = self._most_recent_ancestor_chain_operation(fill_position)

        if empty_position is not None:
            return self._empty_dependencies(
                empty_position,
                child_operations,
                fill_dependency,
                emptied_ancestor=typing.cast(
                    "LastOperationNode",
                    self._most_recent_ancestor_chain_operation(empty_position),
                ),
            )
        if fill_dependency is not None:
            return (fill_dependency,)
        return (self._action_parent_last_operation,)

    def _empty_dependencies(
        self,
        empty_position: tuple[str, ...],
        child_operations: ParticleChildOperations,
        fill_dependency: LastOperationNode | None,
        *,
        emptied_ancestor: LastOperationNode,
    ) -> tuple[
        LastOperationNode | CallerEmptyRuleDependenciesNode,
        ...,
    ]:
        """Apply the Empty Rule with the known most recent operation on the position or its parent names."""
        dependencies = child_operations.determine_empty_rule_dependencies(
            empty_position,
            fill_dependency,
            emptied_ancestor,
        )
        if dependencies.caller_dependencies is None:
            return dependencies.local_dependencies
        return (
            *dependencies.local_dependencies,
            self._add_caller_empty_rule_dependencies(dependencies.caller_dependencies),
        )

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
        # The callee's destruction cascade empties a child position of a
        # particle that the callee received through a position requirement.
        if isinstance(
            caller_empty_rule_dependencies,
            CallerChildPositionEmptyRuleDependencies,
        ):
            return self._substitute_empty_rule_dependencies_for_child_position(
                caller_empty_rule_dependencies.emptied_position,
                callee_requirement_binding,
            )
        particle_dependencies = typing.cast(
            "CallerParticleEmptyRuleDependencies",
            caller_empty_rule_dependencies,
        )
        child_operations = (
            callee_requirement_binding.child_operations.operations_not_on_same_paths_as(
                particle_dependencies.dependency_child_positions
            )
        )
        candidates: set[LastOperationNode] = {
            child_operation.operation for child_operation in child_operations
        }
        for requirement in particle_dependencies.dependency_requirements:
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
                and not particle_dependencies.dependency_child_positions
            ):
                # callee_requirement_binding.operation is the operation on the emptied
                # position. When there are no later child-position operations, it
                # remains the required dependency per the Empty Rule.
                candidates.add(callee_requirement_binding.operation)
            return CallerEmptyRuleSubstitution(
                operation_graph_model.apply_empty_rule_reduction(candidates),
                None,
            )

        # If this action received the particle from its caller, some operations
        # required by the Empty Rule may belong to that caller and must be propagated.
        # Apply what we can of the Empty Rule now to this caller's operations before
        # propagating dependencies from this caller's occupied requirement to its caller.
        dependencies = operation_graph_model.apply_empty_rule_reduction(candidates)
        dependency_nodes: list[PrecedingChildOperationNode] = []
        dependency_requirements: list[tuple[str, ...]] = []
        dependency_child_positions = set(
            callee_requirement_binding.child_operations.child_position_set()
        )
        dependency_child_positions.update(
            particle_dependencies.dependency_child_positions
        )
        for node in dependencies:
            if isinstance(node, RequirementNode):
                dependency_requirements.append(node.requirement_position)
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
            CallerParticleEmptyRuleDependencies(
                requirement_position=requirement_position_in_caller,
                dependency_child_positions=frozenset(dependency_child_positions),
                dependency_requirements=tuple(dependency_requirements),
            ),
        )

    def _substitute_empty_rule_dependencies_for_child_position(
        self,
        emptied_position: tuple[str, ...],
        callee_requirement_binding: RequirementBinding,
    ) -> CallerEmptyRuleSubstitution:
        """Substitute caller dependencies for emptying a required particle's child position."""
        dependencies = (
            callee_requirement_binding.child_operations.empty_rule_dependencies_for(
                emptied_position
            )
        )
        # Before triggering the callee, the direct caller operated on that child
        # position or one of its parent or child names.
        if dependencies:
            return CallerEmptyRuleSubstitution(
                dependencies,
                None,
            )
        requirement_position_in_caller = self._occupied_requirement_position(
            callee_requirement_binding
        )
        # The direct caller created or moved the required particle, or triggered
        # an action that guaranteed it.
        if requirement_position_in_caller is None:
            return CallerEmptyRuleSubstitution(
                (callee_requirement_binding.operation,),
                None,
            )
        # The direct caller received the required particle through its own
        # position requirement, so its caller may have operated on the child.
        return CallerEmptyRuleSubstitution(
            (),
            CallerChildPositionEmptyRuleDependencies(
                requirement_position=requirement_position_in_caller,
                emptied_position=emptied_position,
            ),
        )

    def _occupied_requirement_position(
        self, binding: RequirementBinding
    ) -> tuple[str, ...] | None:
        """Return the occupied requirement position represented by ``binding``."""
        node = binding.operation
        if not isinstance(node, RequirementNode):
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
            if not ast.is_prefix(particle_position, position):
                continue
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
        """Record the destruction of one particle."""
        return self._record_destroy(DestroyNode, target, preceding_child_operations)

    def record_destroy_if_occupied(
        self,
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> DestroyIfOccupiedNode:
        """Record a particle destruction conditional on its position being occupied."""
        return self._record_destroy(
            DestroyIfOccupiedNode,
            target,
            preceding_child_operations,
        )

    def _record_destroy[DestroyNodeT: DestroyNode](
        self,
        node_type: type[DestroyNodeT],
        target: ast.PositionReference,
        preceding_child_operations: PrecedingChildOperations,
    ) -> DestroyNodeT:
        """Record one particle destruction."""
        child_operations = ParticleChildOperations.from_preceding_operations(
            preceding_child_operations
        )
        key = target.canonical_chained_name_tuple
        depends_on = self._empty_dependencies(
            key,
            child_operations,
            None,
            emptied_ancestor=typing.cast(
                "LastOperationNode",
                self._most_recent_ancestor_chain_operation(key),
            ),
        )
        node = node_type(
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
        nested_triggers: tuple[ActionTrigger, ...],
        guaranteed_positions: Iterable[
            tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]
        ],
        *,
        guarantee_action_chain: tuple[str, ...],
        operation_graph_action_chain: tuple[str, ...],
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
        for caller_position, operation_positions_in_guarantee in guaranteed_positions:
            node = GuaranteeNode(
                node_id=len(self._nodes),
                trigger=trigger,
                nested_triggers=nested_triggers,
                guaranteed_position=ast.chain_in_callee(
                    operation_graph_action_chain, caller_position
                ),
                depends_on=(trigger.trigger_operation,),
                operation_positions=tuple(
                    ast.chain_in_caller(guarantee_action_chain, operation_position)
                    for operation_position in operation_positions_in_guarantee
                ),
            )
            self._nodes.append(node)
            self._last_operation[caller_position] = node
            nodes[caller_position] = node
        return nodes

    def record_guaranteed_positions(self, positions: Iterable[tuple[str, ...]]):
        """Record guarantees published by this action's Particle Operations."""
        positions_by_operation: dict[PositionOperationNode, list[tuple[str, ...]]] = {}
        for position in positions:
            node = self._last_operation.get(position)
            if not isinstance(node, PositionOperationNode):
                continue
            positions_by_operation.setdefault(node, []).append(position)
        self.guaranteed_positions_by_operation = {
            operation: tuple(guaranteed_positions)
            for operation, guaranteed_positions in positions_by_operation.items()
        }


@dataclass(frozen=True, slots=True)
class _CalleeGuaranteeResolution:
    """A direct callee through which a guarantee resolves."""

    trigger: ActionTrigger
    callee_resolution: _GuaranteeResolution


type _GuaranteeResolution = PositionOperationNode | _CalleeGuaranteeResolution


@dataclass(slots=True)
class GuaranteePath:
    """Action Triggerings from a guarantee to its publishing Particle Operation."""

    triggers: list[ActionTrigger]
    operation: PositionOperationNode


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

    def resolve_guarantee(self, guarantee: GuaranteeNode) -> GuaranteePath:
        """Resolve one guarantee to its Particle Operation through callee graphs."""
        triggers = [guarantee.trigger, *guarantee.nested_triggers]
        resolution = self._resolve_guaranteed_position(
            triggers[-1].callee_action_name, guarantee.guaranteed_position
        )
        while isinstance(resolution, _CalleeGuaranteeResolution):
            triggers.append(resolution.trigger)
            resolution = resolution.callee_resolution
        return GuaranteePath(triggers, resolution)

    def _resolve_guaranteed_position(
        self, action: ast.GlobalTypedName, position: tuple[str, ...]
    ) -> _GuaranteeResolution:
        unresolved: list[tuple[str, tuple[str, ...], tuple[ActionTrigger, ...]]] = []
        while True:
            action_name = action.full_typed_name
            action_resolutions = self._guarantee_resolutions[action_name]
            cached = action_resolutions.get(position)
            if cached is not None:
                resolution = cached
                break

            graph = self[action]
            node = graph.last_operation_on_position_or_parents(position)
            match node:
                case PositionOperationNode():
                    resolution = node
                    action_resolutions[position] = resolution
                    break
                case GuaranteeNode():
                    triggers = (node.trigger, *node.nested_triggers)
                    action = triggers[-1].callee_action_name
                    next_position = node.guaranteed_position
                case RequirementNode():
                    trigger = graph.last_trigger_using_requirement(node)
                    triggers = (trigger,)
                    action = trigger.callee_action_name
                    next_position = ast.chain_in_callee(trigger.action_chain, position)
            unresolved.append((action_name, position, triggers))
            position = next_position

        for action_name, position, triggers in reversed(unresolved):
            for trigger in reversed(triggers):
                resolution = _CalleeGuaranteeResolution(trigger, resolution)
            self._guarantee_resolutions[action_name][position] = resolution
        return resolution
