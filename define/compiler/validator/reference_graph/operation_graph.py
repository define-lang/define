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
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class _UnrecordedDestructionPosition:
    """One caller-known occupied position not yet recorded in the graph."""

    newly_occupied_child: operation_graph_model.ContributedDestructionPosition
    destruction_position: tuple[str, ...]


@dataclass(slots=True)
class _ContributedDestructionRelationships:
    """Parent and child relationships among Destroys of newly known occupied children for a single Destruction Contract."""

    dependency_indexes_by_position: list[tuple[int, ...]]
    completion_operation_indexes: list[int]
    contribution_positions: set[tuple[str, ...]]

    @classmethod
    def from_unrecorded_positions(
        cls,
        unrecorded_positions: list[_UnrecordedDestructionPosition],
        destroyed_particle_key: tuple[str, ...],
    ) -> _ContributedDestructionRelationships:
        dependency_indexes_by_position: list[tuple[int, ...]] = []
        completion_operation_indexes: list[int] = []
        contribution_positions: set[tuple[str, ...]] = set()
        for operation_index, unrecorded_position in enumerate(unrecorded_positions):
            position_key = unrecorded_position.newly_occupied_child.position.canonical_chained_name_tuple
            dependency_indexes: list[int] = []
            # Cascade order places child-position Destroys immediately before their
            # parent-position Destroy. Pop their indexes from the completion stack
            # and retain them as dependencies of the parent-position Destroy.
            while completion_operation_indexes:
                completion_operation_index = completion_operation_indexes[-1]
                completion_position_key = unrecorded_positions[
                    completion_operation_index
                ].newly_occupied_child.position.canonical_chained_name_tuple
                if not ast.is_prefix(position_key, completion_position_key):
                    break
                dependency_indexes.append(completion_operation_indexes.pop())
            # A Destroy without caller-contributed child-position Destroys begins a
            # separate caller contribution. Finding every such position first lets
            # one retained child-operation snapshot be partitioned in a single pass.
            if not dependency_indexes:
                contribution_positions.add(position_key[len(destroyed_particle_key) :])
            dependency_indexes_by_position.append(tuple(dependency_indexes))
            completion_operation_indexes.append(operation_index)
        return cls(
            dependency_indexes_by_position,
            completion_operation_indexes,
            contribution_positions,
        )


@dataclass(slots=True)
class _RecordedDestructionContribution:
    """Operations recorded for one caller contribution."""

    node: operation_graph_model.DestructionContributionNode
    operations: list[operation_graph_model.DestructionFragmentDestroyNode] = field(
        default_factory=list
    )
    completion_operations: list[
        operation_graph_model.DestructionFragmentDestroyNode
    ] = field(default_factory=list)


class OperationGraph:
    """An append-only dependency graph of one action's particle operations."""

    def __init__(self, action: ast.GlobalTypedName):
        """Create an empty operation graph."""
        self.action: ast.GlobalTypedName = action
        self._nodes: list[operation_graph_model.OperationNode] = []
        # Finding the most recent operation on a position or one of its parent
        # names otherwise slices and probes every prefix of the position. Deep
        # requirement propagation extends these names repeatedly, so copying all
        # those prefixes became a material part of compilation time.
        #
        # Most matching operations were written only a few writes before the
        # lookup. Retaining four writes found 95.050% of lookups in the default
        # deep-pipeline workload and 98.652% in a more concentrated version of
        # that workload. Two and three writes missed recurring matches at
        # distances three and four. Eight writes found only another 0.117% and
        # 0.008%, respectively, while doubling retained references, doing twice
        # as many comparisons on a miss, and running slower on both concentrated
        # and deliberately interleaved workloads. Four is therefore the smallest
        # measured bound at the useful performance knee, not a language semantic
        # invariant.
        #
        # The index is a flat tuple of four alternating key and operation pairs,
        # so its memory is fixed at eight retained references per action. A prior
        # prefix-tree experiment made representative workloads slower and used
        # unbounded memory as position depth and breadth grew. Keep this mapping
        # as the exact fallback: valid programs can interleave writes without
        # temporal locality, and any index miss must still return the same result
        # as the complete prefix scan.
        #
        # Every mapping write must go through _set_last_operation so the tuple is
        # an exact suffix of write history. It is searched newest first. A
        # matching retained write is necessarily newer than every evicted write,
        # so it is safe to return immediately; when none matches, the complete
        # mapping scan determines the answer.
        self._recent_last_operations: tuple[
            tuple[str, ...] | operation_graph_model.LastOperationNode, ...
        ] = ()
        # A position's canonical chained name -> its last body operation or
        # recorded requirement.
        self._last_operation: dict[
            tuple[str, ...], operation_graph_model.LastOperationNode
        ] = {}
        # Every Action Execution this action performs, in the order it performs them.
        # One operation can fire more than one (creating a particle fires every
        # constructor it has).
        self._executions: list[operation_graph_model.ActionExecution] = []
        # Every local position has the position of the particle this action is
        # assigned to as a transitive parent from the caller's perspective.
        self._action_parent_last_operation: operation_graph_model.ActionParentLastOperationNode = operation_graph_model.ActionParentLastOperationNode(
            node_id=len(self._nodes),
            depends_on=(),
        )
        self._nodes.append(self._action_parent_last_operation)
        self.guaranteed_positions_by_operation: dict[
            operation_graph_model.PositionOperationNode, tuple[tuple[str, ...], ...]
        ] = {}
        self._destructions: dict[
            operation_graph_model.DestructionFact,
            operation_graph_model.OperationGraphDestruction,
        ] = {}
        self._contributed_destruction_fragments_by_direct_callee_execution: dict[
            operation_graph_model.ActionExecution,
            list[operation_graph_model.ContributedDestructionFragment],
        ] = {}
        self._executions_propagating_destruction_to_caller: set[
            operation_graph_model.ActionExecution
        ] = set()

    @property
    def nodes(self) -> Sequence[operation_graph_model.OperationNode]:
        """Every node, in creation order."""
        return self._nodes

    def last_operation_on_position(
        self, key: tuple[str, ...]
    ) -> (
        operation_graph_model.PrecedingChildOperationNode
        | operation_graph_model.RequirementNode
    ):
        """Return the last operation recorded on exactly ``key``."""
        return self._last_operation[key]

    def last_operation_on_position_or_parents(
        self, key: tuple[str, ...]
    ) -> (
        operation_graph_model.PrecedingChildOperationNode
        | operation_graph_model.RequirementNode
    ):
        """Return the last operation on ``key`` or one of its parent names."""
        last_operation: operation_graph_model.LastOperationNode | None = None
        for length in range(len(key), 0, -1):
            operation = self._last_operation.get(key[:length])
            if operation is not None and (
                last_operation is None
                or last_operation.operation_order < operation.operation_order
            ):
                last_operation = operation
        if last_operation is None:
            raise KeyError(key)
        return last_operation

    def body_touched_key(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly this key.

        A recorded RequirementNode stands in for a caller operation, not a
        body operation, so it does not count as the body touching the position.
        """
        node = self._last_operation.get(key)
        return node is not None and not isinstance(
            node, operation_graph_model.RequirementNode
        )

    def record_requirement(
        self,
        position: ast.PositionReference,
        required_state: action_contract.PositionOccupancyState,
    ):
        """Record the caller operation represented by a position requirement."""
        key = position.canonical_chained_name_tuple
        ancestor = typing.cast(
            "operation_graph_model.RequirementNode | None",
            self._most_recent_ancestor_chain_operation(key[:-1]),
        )
        if ancestor is None:
            ancestor = self._action_parent_last_operation
        node = operation_graph_model.RequirementNode(
            node_id=len(self._nodes),
            required_state=required_state,
            requirement_position=key,
            depends_on=(ancestor,),
        )
        self._nodes.append(node)
        self._set_last_operation(key, node)

    def record_action_execution(
        self,
        callee: ast.ActionReference,
        acting_on_position: ast.PositionReference,
        requirements_in_caller: Sequence[action_contract.PositionRequirementInCaller],
        *,
        is_destructor: bool,
        acting_on_preceding_child_operations: operation_graph_model.PrecedingChildOperations,
        required_preceding_child_operations: Iterable[
            operation_graph_model.PrecedingChildOperations
        ],
    ) -> operation_graph_model.ActionExecution:
        """Record that this action triggers ``callee``, returning that Action Execution.

        The firing operation is the one that filled ``acting_on_position`` (a
        trigger position for an action, or the action being operated on by a
        constructor/destructor).

        ``requirements_in_caller`` pairs each callee requirement with its
        position from the caller's perspective. The child-operation arguments
        identify operations responsible for the current state of the particles'
        child positions.
        """
        acting_on_position_key = acting_on_position.canonical_chained_name_tuple
        if is_destructor:
            # Need to check the parents because destructors trigger on child
            # positions of the passed-in particle, so it's the last operation
            # on their parent that matters.
            firing_operation = self.last_operation_on_position_or_parents(
                acting_on_position_key
            )
        else:
            firing_operation = self.last_operation_on_position(acting_on_position_key)
        callee_action_key = callee.canonical_chained_name_tuple
        bindings: dict[tuple[str, ...], operation_graph_model.RequirementBinding] = {}
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
            operation_graph_model.ParticleChildOperations.from_preceding_operations(
                acting_on_preceding_child_operations
            ),
            firing_operation,
        )
        for requirement_in_caller, preceding_child_operations in zip(
            requirements_in_caller,
            required_preceding_child_operations,
            strict=True,
        ):
            requirement = requirement_in_caller.requirement
            caller_position = requirement_in_caller.caller_position
            caller_position_key = caller_position.canonical_chained_name_tuple
            requirement_key = requirement.position.canonical_chained_name_tuple
            binding_operation = self._requirement_binding_operation(caller_position_key)
            if binding_operation is not None:
                bindings[requirement_key] = self._requirement_binding(
                    operation_graph_model.ParticleChildOperations.from_preceding_operations(
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
                "operation_graph_model.LastOperationNode",
                self._most_recent_ancestor_chain_operation(
                    action_parent_position.canonical_chained_name_tuple
                ),
            )
        execution = operation_graph_model.ActionExecution(
            callee=callee,
            trigger_operation=firing_operation,
            bindings=bindings,
            action_parent_last_operation=action_parent_last_operation,
        )
        self._executions.append(execution)
        return execution

    def _requirement_binding(
        self,
        child_operations: operation_graph_model.ParticleChildOperations,
        operation: operation_graph_model.LastOperationNode,
    ) -> operation_graph_model.RequirementBinding:
        """Return the caller dependencies that satisfy a callee requirement."""
        # A move that brought the whole particle here already depends on every
        # older child operation, so retaining them would add redundant edges.
        if isinstance(
            operation, operation_graph_model.MoveNode
        ) and child_operations.all_precede(operation):
            child_operations = operation_graph_model.ParticleChildOperations()
        return operation_graph_model.RequirementBinding(operation, child_operations)

    @property
    def executions(self) -> Sequence[operation_graph_model.ActionExecution]:
        """Every action this action triggers, in the order it triggers them."""
        return self._executions

    def destruction_for_fact(
        self, destruction_fact: operation_graph_model.DestructionFact
    ) -> operation_graph_model.OperationGraphDestruction:
        """Return the destruction recorded for one Destruction Fact."""
        return self._destructions[destruction_fact]

    @property
    def propagates_destruction_facts(self) -> bool:
        """Whether this action propagates any Destruction Fact to its caller."""
        return any(
            destruction.is_propagated_to_caller
            for destruction in self._destructions.values()
        )

    def contributed_destruction_fragments_for(
        self, direct_callee_execution: operation_graph_model.ActionExecution
    ) -> Sequence[operation_graph_model.ContributedDestructionFragment]:
        """Return destruction fragments contributed around one Action Execution."""
        return self._contributed_destruction_fragments_by_direct_callee_execution.get(
            direct_callee_execution, ()
        )

    def propagates_destruction_from_execution_to_caller(
        self, execution: operation_graph_model.ActionExecution
    ) -> bool:
        """Return whether a Destruction Fact from the Action Execution's callee is propagated to this action's caller."""
        return execution in self._executions_propagating_destruction_to_caller

    def record_destruction_fact_destroy(
        self,
        destruction_fact: operation_graph_model.DestructionFact,
        target: ast.PositionReference,
        preceding_child_operations: operation_graph_model.PrecedingChildOperations,
        *,
        propagate_to_caller: bool,
    ) -> operation_graph_model.DestructionFactDestroyNode:
        """Record one cascade Destroy belonging to a Destruction Fact."""
        target_key = target.canonical_chained_name_tuple
        dependency_before_caller_contribution = typing.cast(
            "operation_graph_model.LastOperationNode",
            self._most_recent_ancestor_chain_operation(target_key),
        )
        child_operations = (
            operation_graph_model.ParticleChildOperations.from_preceding_operations(
                preceding_child_operations
            )
        )
        node = operation_graph_model.DestructionFactDestroyNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=self._destruction_dependencies(
                target,
                child_operations,
                dependency_before_caller_contribution,
            ),
            destruction_fact=destruction_fact,
            destruction_position=target_key[
                len(
                    destruction_fact.destroyed_position_in_destroyer.canonical_chained_name_tuple
                ) :
            ],
            dependencies_before_caller_contribution=(
                dependency_before_caller_contribution,
            ),
            # An empty relative position names the destroyed particle itself.
            # Preserve its child-operation dependencies so inserting caller-contributed
            # Destroys does not replace dependencies on the callee's child operations.
            dependencies_after_caller_contribution=(
                child_operations.empty_rule_dependencies_for(())
            ),
        )
        self._record_destroy_node(node)
        destruction = self._get_or_create_destruction(destruction_fact)
        destruction.operations_by_position[node.destruction_position] = node
        if propagate_to_caller:
            destruction.is_propagated_to_caller = True
        return node

    def record_contributed_destruction_fragment(
        self,
        execution: operation_graph_model.ActionExecution,
        newly_occupied_children: operation_graph_model.DestructionContractNewlyOccupiedChildren,
    ):
        """Record only the ordinary child Destroys newly known by this caller."""
        destruction_fact = newly_occupied_children.destruction_fact
        destruction = self._get_or_create_destruction(destruction_fact)
        if newly_occupied_children.is_propagated_to_caller:
            destruction.is_propagated_to_caller = True
            destruction.direct_callee_execution = execution
            self._executions_propagating_destruction_to_caller.add(execution)
        fact_key = destruction_fact.destroyed_position_in_destroyer.canonical_chained_name_tuple
        destroyed_position_key = newly_occupied_children.destroyed_position_in_destroying_action.canonical_chained_name_tuple
        destroyed_position_relative_to_fact = destroyed_position_key[len(fact_key) :]
        unrecorded_positions = self._unrecorded_contributed_destruction_positions(
            execution,
            newly_occupied_children,
            destruction,
            destroyed_position_relative_to_fact,
        )
        if not unrecorded_positions:
            return
        destroyed_particle_key = newly_occupied_children.destroyed_particle_position.canonical_chained_name_tuple
        relationships = _ContributedDestructionRelationships.from_unrecorded_positions(
            unrecorded_positions,
            destroyed_particle_key,
        )
        fragment = self._record_contributed_destruction_operations(
            execution,
            newly_occupied_children,
            destruction,
            destroyed_position_relative_to_fact,
            destroyed_particle_key,
            unrecorded_positions,
            relationships,
        )
        self._contributed_destruction_fragments_by_direct_callee_execution.setdefault(
            execution, []
        ).append(fragment)

    def _unrecorded_contributed_destruction_positions(
        self,
        execution: operation_graph_model.ActionExecution,
        newly_occupied_children: operation_graph_model.DestructionContractNewlyOccupiedChildren,
        destruction: operation_graph_model.OperationGraphDestruction,
        destroyed_position_relative_to_fact: tuple[str, ...],
    ) -> list[_UnrecordedDestructionPosition]:
        unrecorded_positions: list[_UnrecordedDestructionPosition] = []
        for newly_occupied_child in newly_occupied_children.children:
            destruction_position = (
                *destroyed_position_relative_to_fact,
                *newly_occupied_child.position_relative_to_destroyed_particle,
            )
            # Destroying a caller-supplied parent records Destruction Contracts
            # for both the parent and its caller-supplied children. Those contracts
            # can expose the same caller-known descendant through one Action Execution,
            # but the descendant is destroyed once.
            existing_operation = destruction.operations_by_position.get(
                destruction_position
            )
            if (
                isinstance(
                    existing_operation,
                    operation_graph_model.DestructionFragmentDestroyNode,
                )
                and existing_operation.direct_callee_execution is execution
            ):
                continue
            unrecorded_positions.append(
                _UnrecordedDestructionPosition(
                    newly_occupied_child,
                    destruction_position=destruction_position,
                )
            )
        return unrecorded_positions

    def _record_contributed_destruction_operations(
        self,
        execution: operation_graph_model.ActionExecution,
        newly_occupied_children: operation_graph_model.DestructionContractNewlyOccupiedChildren,
        destruction: operation_graph_model.OperationGraphDestruction,
        destroyed_position_relative_to_fact: tuple[str, ...],
        destroyed_particle_key: tuple[str, ...],
        unrecorded_positions: list[_UnrecordedDestructionPosition],
        relationships: _ContributedDestructionRelationships,
    ) -> operation_graph_model.ContributedDestructionFragment:
        destruction_fact = newly_occupied_children.destruction_fact
        # By the Empty Rule, a caller-contributed Destroy depends on the caller's
        # earlier operations on relevant child positions of the destroyed particle.
        # The Action Execution binding records those operations.
        destroyed_particle_position_in_callee = ast.chain_in_callee(
            execution.action_chain, destroyed_particle_key
        )
        child_operations = execution.bindings[
            destroyed_particle_position_in_callee
        ].child_operations
        # Each separate contribution needs only the preceding operations on child
        # positions of the position it destroys. Partition once to avoid searching
        # all retained child operations for every contribution.
        child_operations_by_contribution_position = child_operations.partition_for_child_positions_without_parent_child_relationships(
            relationships.contribution_positions
        )
        operations: list[operation_graph_model.DestructionFragmentDestroyNode] = []
        contributions: list[_RecordedDestructionContribution] = []
        # Record which contributions contain each Destroy. When a later
        # parent-position Destroy depends on those child-position Destroys, add the
        # parent-position Destroy to the same contributions.
        contributions_by_operation: list[
            tuple[_RecordedDestructionContribution, ...]
        ] = []
        for operation_index, unrecorded_position in enumerate(unrecorded_positions):
            newly_occupied_child = unrecorded_position.newly_occupied_child
            position = newly_occupied_child.position
            position_key = position.canonical_chained_name_tuple
            callee_destroy_position = (
                *destroyed_position_relative_to_fact,
                *newly_occupied_child.callee_destroy_position_relative_to_destroyed_particle,
            )
            dependency_indexes = relationships.dependency_indexes_by_position[
                operation_index
            ]
            # Validation records cascade Destroys child before parent, so these
            # indexes always refer to operations already constructed in this loop.
            local_dependencies: list[
                operation_graph_model.DestructionFragmentDestroyNode
            ] = [
                operations[dependency_index] for dependency_index in dependency_indexes
            ]
            operation_contributions = self._contributions_for_dependencies(
                dependency_indexes,
                contributions_by_operation,
            )
            if local_dependencies:
                # A parent-position Destroy continues the contributions begun by its
                # child-position Destroys rather than beginning another contribution.
                dependencies: tuple[operation_graph_model.OperationNode, ...] = tuple(
                    local_dependencies
                )
                dependencies_before_caller_contribution = dependencies
                dependencies_after_caller_contribution = dependencies
            else:
                # A caller-known occupied child position with no contributed child
                # Destroy must begin a separate contribution because no existing
                # contribution contains it.
                contribution_position = position_key[len(destroyed_particle_key) :]
                contribution = operation_graph_model.DestructionContributionNode(
                    node_id=len(self._nodes),
                    depends_on=self._destruction_dependencies(
                        position,
                        child_operations_by_contribution_position[
                            contribution_position
                        ],
                        typing.cast(
                            "operation_graph_model.LastOperationNode",
                            self._most_recent_ancestor_chain_operation(position_key),
                        ),
                    ),
                    execution=execution,
                    destruction_fact=destruction_fact,
                    callee_destroy_position=callee_destroy_position,
                )
                self._nodes.append(contribution)
                recorded_contribution = _RecordedDestructionContribution(contribution)
                contributions.append(recorded_contribution)
                operation_contributions.append(recorded_contribution)
                dependencies = (contribution,)
                dependencies_before_caller_contribution = contribution.depends_on
                dependencies_after_caller_contribution = ()
            # The resolver needs the same position relative to the original
            # destroying action even when a higher caller discovered this child.
            suffix = position.typed_names[
                len(newly_occupied_children.destroyed_particle_position.typed_names) :
            ]
            target_in_destroying_action = newly_occupied_children.destroyed_position_in_destroying_action.with_position_suffix(
                *suffix
            )
            operation = operation_graph_model.DestructionFragmentDestroyNode(
                node_id=len(self._nodes),
                target=position,
                depends_on=dependencies,
                destruction_fact=destruction_fact,
                destruction_position=unrecorded_position.destruction_position,
                dependencies_before_caller_contribution=dependencies_before_caller_contribution,
                dependencies_after_caller_contribution=dependencies_after_caller_contribution,
                direct_callee_execution=execution,
                target_in_destroying_action=target_in_destroying_action,
            )
            self._nodes.append(operation)
            operations.append(operation)
            contributions_by_operation.append(tuple(operation_contributions))
            # When a parent-position Destroy depends on a child-position Destroy,
            # add the parent-position Destroy to every contribution that contains
            # the child-position Destroy.
            for recorded_contribution in operation_contributions:
                recorded_contribution.operations.append(operation)
            destruction.operations_by_position[operation.destruction_position] = (
                operation
            )
        # The remaining indexes identify Destroys with no contributed parent-position
        # Destroy, so each contribution's callee Destroy depends on them.
        for operation_index in relationships.completion_operation_indexes:
            operation = operations[operation_index]
            for recorded_contribution in contributions_by_operation[operation_index]:
                recorded_contribution.completion_operations.append(operation)
        contributed_destructions: list[
            operation_graph_model.ContributedDestruction
        ] = []
        for recorded_contribution in contributions:
            contributed_destructions.append(
                operation_graph_model.ContributedDestruction(
                    recorded_contribution.node,
                    tuple(recorded_contribution.operations),
                    tuple(recorded_contribution.completion_operations),
                )
            )
        contribution_dependencies: list[operation_graph_model.OperationNode] = []
        for contribution in contributions:
            contribution_dependencies.extend(contribution.node.depends_on)
        return operation_graph_model.ContributedDestructionFragment(
            tuple(contribution_dependencies),
            tuple(operations),
            tuple(contributed_destructions),
        )

    @staticmethod
    def _contributions_for_dependencies(
        dependency_indexes: Sequence[int],
        contributions_by_operation: Sequence[
            tuple[_RecordedDestructionContribution, ...]
        ],
    ) -> list[_RecordedDestructionContribution]:
        contributions: list[_RecordedDestructionContribution] = []
        for dependency_index in dependency_indexes:
            contributions.extend(contributions_by_operation[dependency_index])
        return contributions

    def _get_or_create_destruction(
        self,
        destruction_fact: operation_graph_model.DestructionFact,
    ) -> operation_graph_model.OperationGraphDestruction:
        destruction = self._destructions.get(destruction_fact)
        if destruction is None:
            destruction = operation_graph_model.OperationGraphDestruction()
            self._destructions[destruction_fact] = destruction
        return destruction

    def _requirement_binding_operation(
        self, caller_position_key: tuple[str, ...]
    ) -> operation_graph_model.LastOperationNode | None:
        """Return the operation on ``caller_position_key`` that satisfies a callee requirement, or None."""
        operation = self._last_operation.get(caller_position_key)
        if operation is not None:
            return operation
        ancestor_operation = self._most_recent_ancestor_chain_operation(
            caller_position_key
        )
        # A move of a parent position also put this position in its current state.
        if isinstance(ancestor_operation, operation_graph_model.MoveNode):
            return ancestor_operation
        return None

    def _operation_dependencies(
        self,
        *,
        fill_position: tuple[str, ...],
        empty_position: tuple[str, ...] | None = None,
        child_operations: operation_graph_model.ParticleChildOperations | None = None,
    ) -> tuple[operation_graph_model.OperationNode, ...]:
        """Return dependencies required before optionally emptying and filling positions."""
        if child_operations is None:
            child_operations = operation_graph_model.ParticleChildOperations()
        # Filling a position waits on the most recent operation on that
        # position and its parent names, so the parent particle is present.
        fill_dependency = self._most_recent_ancestor_chain_operation(fill_position)

        if empty_position is not None:
            return self._empty_dependencies(
                empty_position,
                child_operations,
                fill_dependency,
                emptied_ancestor=typing.cast(
                    "operation_graph_model.LastOperationNode",
                    self._most_recent_ancestor_chain_operation(empty_position),
                ),
            )
        if fill_dependency is not None:
            return (fill_dependency,)
        return (self._action_parent_last_operation,)

    def _empty_dependencies(
        self,
        empty_position: tuple[str, ...],
        child_operations: operation_graph_model.ParticleChildOperations,
        fill_dependency: operation_graph_model.LastOperationNode | None,
        *,
        emptied_ancestor: operation_graph_model.LastOperationNode,
    ) -> tuple[
        operation_graph_model.LastOperationNode
        | operation_graph_model.CallerEmptyRuleDependenciesNode,
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
    ) -> operation_graph_model.LastOperationNode | None:
        """Return the most recent operation on ``position``'s ancestor chain."""
        # Check recent writes first to avoid slicing and probing every position
        # prefix. The first match is newer than every omitted write, so it is exact.
        for index in range(len(self._recent_last_operations) - 2, -1, -2):
            key = typing.cast("tuple[str, ...]", self._recent_last_operations[index])
            if len(key) <= len(position) and position[: len(key)] == key:
                return typing.cast(
                    "operation_graph_model.LastOperationNode",
                    self._recent_last_operations[index + 1],
                )
        ancestor: operation_graph_model.LastOperationNode | None = None
        for length in range(1, len(position) + 1):
            key = position[:length]
            existing = self._last_operation.get(key)
            # Most parent names have no operation; among those that do, a newer
            # operation wins even when it is on a more-distant parent name.
            if existing is not None and (
                ancestor is None or ancestor.operation_order < existing.operation_order
            ):
                ancestor = existing
        return ancestor

    def _set_last_operation(
        self,
        key: tuple[str, ...],
        operation: operation_graph_model.LastOperationNode,
    ):
        """Record the last operation and retain the four most recent writes."""
        self._last_operation[key] = operation
        self._recent_last_operations = (
            *self._recent_last_operations[-6:],
            key,
            operation,
        )

    def _add_caller_empty_rule_dependencies(
        self,
        caller_empty_rule_dependencies: operation_graph_model.CallerEmptyRuleDependencies,
    ) -> operation_graph_model.CallerEmptyRuleDependenciesNode:
        """Add and return the caller contribution for emptying a required particle."""
        node = operation_graph_model.CallerEmptyRuleDependenciesNode(
            node_id=len(self._nodes),
            depends_on=(),
            caller_empty_rule_dependencies=caller_empty_rule_dependencies,
        )
        self._nodes.append(node)
        return node

    def record_create(
        self, target: ast.PositionReference
    ) -> operation_graph_model.CreateNode:
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(fill_position=key)
        node = operation_graph_model.CreateNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=depends_on,
        )
        self._nodes.append(node)
        self._set_last_operation(key, node)
        return node

    def record_move(
        self,
        source: ast.PositionReference,
        target: ast.PositionReference,
        preceding_child_operations: operation_graph_model.PrecedingChildOperations,
    ) -> operation_graph_model.MoveNode:
        """Record a body move from ``source`` to ``target``."""
        child_operations = (
            operation_graph_model.ParticleChildOperations.from_preceding_operations(
                preceding_child_operations
            )
        )
        source_key = source.canonical_chained_name_tuple
        target_key = target.canonical_chained_name_tuple
        depends_on = self._operation_dependencies(
            empty_position=source_key,
            fill_position=target_key,
            child_operations=child_operations,
        )
        node = operation_graph_model.MoveNode(
            node_id=len(self._nodes),
            target=target,
            source=source,
            depends_on=depends_on,
        )
        self._nodes.append(node)
        self._set_last_operation(source_key, node)
        self._set_last_operation(target_key, node)
        return node

    def record_destroy(
        self,
        target: ast.PositionReference,
        preceding_child_operations: operation_graph_model.PrecedingChildOperations,
    ) -> operation_graph_model.DestroyNode:
        """Record the destruction of one particle."""
        key = target.canonical_chained_name_tuple
        child_operations = (
            operation_graph_model.ParticleChildOperations.from_preceding_operations(
                preceding_child_operations
            )
        )
        node = operation_graph_model.DestroyNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=self._destruction_dependencies(
                target,
                child_operations,
                typing.cast(
                    "operation_graph_model.LastOperationNode",
                    self._most_recent_ancestor_chain_operation(key),
                ),
            ),
        )
        self._record_destroy_node(node)
        return node

    def _destruction_dependencies(
        self,
        target: ast.PositionReference,
        child_operations: operation_graph_model.ParticleChildOperations,
        emptied_ancestor: operation_graph_model.LastOperationNode,
    ) -> tuple[operation_graph_model.OperationNode, ...]:
        key = target.canonical_chained_name_tuple
        return self._empty_dependencies(
            key,
            child_operations,
            None,
            emptied_ancestor=emptied_ancestor,
        )

    def _record_destroy_node(self, node: operation_graph_model.DestroyNode):
        """Add a constructed Destroy operation to this graph."""
        self._nodes.append(node)
        self._set_last_operation(node.target.canonical_chained_name_tuple, node)

    def record_guarantees(
        self,
        execution: operation_graph_model.ActionExecution,
        nested_executions: tuple[operation_graph_model.ActionExecution, ...],
        guaranteed_positions: Iterable[
            tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]
        ],
        *,
        guarantee_action_chain: tuple[str, ...],
        operation_graph_action_chain: tuple[str, ...],
    ) -> dict[tuple[str, ...], operation_graph_model.GuaranteeNode]:
        """Record the positions ``execution`` guarantees, as nodes hanging off it.

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
        # Action Execution, eliminating over one million list allocations in the
        # largest profile. It failed to reduce compiler CPU: alternating
        # unprofiled runs averaged 8.013s before and 8.037s after, so the
        # prototype was rejected as a CPU optimization.
        # Generator setup and tuple conversion for every guarantee's operation
        # positions looked costly in the default action-graph full-compiler
        # profile. An August 2026 experiment special-cased a single
        # operation_positions_in_guarantee: it called ast.chain_in_caller once and
        # built the one-element tuple directly, bypassing the generator below.
        # Seven unprofiled default action-graph full-compiler runs showed no
        # measurable wall-time change, and CPU profiles did not corroborate an
        # improvement, so it was rejected.
        nodes: dict[tuple[str, ...], operation_graph_model.GuaranteeNode] = {}
        for caller_position, operation_positions_in_guarantee in guaranteed_positions:
            node = operation_graph_model.GuaranteeNode(
                node_id=len(self._nodes),
                execution=execution,
                nested_executions=nested_executions,
                guaranteed_position=ast.chain_in_callee(
                    operation_graph_action_chain, caller_position
                ),
                depends_on=(execution.trigger_operation,),
                operation_positions=tuple(
                    ast.chain_in_caller(guarantee_action_chain, operation_position)
                    for operation_position in operation_positions_in_guarantee
                ),
            )
            self._nodes.append(node)
            self._set_last_operation(caller_position, node)
            nodes[caller_position] = node
        return nodes

    def record_guaranteed_positions(self, positions: Iterable[tuple[str, ...]]):
        """Record guarantees published by this action's Particle Operations."""
        positions_by_operation: dict[
            operation_graph_model.PositionOperationNode, list[tuple[str, ...]]
        ] = {}
        for position in positions:
            node = self._last_operation.get(position)
            if not isinstance(node, operation_graph_model.PositionOperationNode):
                continue
            positions_by_operation.setdefault(node, []).append(position)
        self.guaranteed_positions_by_operation = {
            operation: tuple(guaranteed_positions)
            for operation, guaranteed_positions in positions_by_operation.items()
        }


@dataclass(slots=True)
class GuaranteePath:
    """Action Executions from a guarantee to its publishing Particle Operation."""

    executions: list[operation_graph_model.ActionExecution]
    operation: operation_graph_model.PositionOperationNode


@typing.final
class OperationGraphs(
    typed_name_dict.TypedNameDict[ast.GlobalTypedName, OperationGraph]
):
    """The operation dependency graphs of every validated action.

    Not thread-safe. Adding an operation graph mutates the inherited mapping
    (which itself is not thread-safe), and resolving cross-graph relationships
    mutates internal lazy caches.
    """

    def __init__(self):
        """Initialize an empty operation-graph collection."""
        super().__init__()
        self._guarantee_resolutions: collections.defaultdict[
            str, dict[tuple[str, ...], operation_graph_model.PositionOperationNode]
        ] = collections.defaultdict(dict)
        self._destruction_dependencies: dict[
            tuple[
                operation_graph_model.ActionExecution,
                operation_graph_model.DestructionFact,
                tuple[str, ...],
            ],
            operation_graph_model.DestructionDependency,
        ] = {}

    def resolve_guarantee(
        self, guarantee: operation_graph_model.GuaranteeNode
    ) -> GuaranteePath:
        """Resolve one guarantee to its Particle Operation through callee graphs."""
        executions = [guarantee.execution, *guarantee.nested_executions]
        action = executions[-1].callee_action_name
        position = guarantee.guaranteed_position
        action_resolutions = self._guarantee_resolutions[action.full_typed_name]
        operation = action_resolutions.get(position)
        if operation is None:
            graph = self[action]
            operation = typing.cast(
                "operation_graph_model.PositionOperationNode",
                graph.last_operation_on_position_or_parents(position),
            )
            action_resolutions[position] = operation
        return GuaranteePath(executions, operation)

    def _resolve_destruction_operation(
        self,
        contribution: operation_graph_model.DestructionContributionNode,
    ) -> operation_graph_model.DestructionOperation:
        """Resolve a Destruction Fact position through direct callees."""
        action = contribution.execution.callee_action_name
        while True:
            graph = self[action]
            destruction = graph.destruction_for_fact(contribution.destruction_fact)
            operation = destruction.operations_by_position.get(
                contribution.callee_destroy_position
            )
            if operation is not None:
                return operation_graph_model.DestructionOperation(
                    graph.action,
                    operation,
                )
            execution = typing.cast(
                "operation_graph_model.ActionExecution",
                destruction.direct_callee_execution,
            )
            action = execution.callee_action_name

    def resolve_destruction_dependency(
        self,
        contribution: operation_graph_model.DestructionContributionNode,
    ) -> operation_graph_model.DestructionDependency:
        """Resolve one caller contribution to the callee Destroy it precedes."""
        dependency_key = (
            contribution.execution,
            contribution.destruction_fact,
            contribution.callee_destroy_position,
        )
        dependency = self._destruction_dependencies.get(dependency_key)
        if dependency is None:
            dependency = operation_graph_model.DestructionDependency(
                contribution.execution,
                self._resolve_destruction_operation(contribution),
            )
            self._destruction_dependencies[dependency_key] = dependency
        return dependency

    def destruction_contributions(
        self,
        graph: OperationGraph,
    ) -> dict[
        operation_graph_model.DestructionDependency,
        operation_graph_model.DestructionContribution,
    ]:
        """Return caller-contributed Destroy boundaries by callee Destroy."""
        contributions: dict[
            operation_graph_model.DestructionDependency,
            operation_graph_model.DestructionContribution,
        ] = {}
        for execution in graph.executions:
            for fragment in graph.contributed_destruction_fragments_for(execution):
                for contributed_destruction in fragment.contributed_destructions:
                    dependency = self.resolve_destruction_dependency(
                        contributed_destruction.contribution_node
                    )
                    contribution = contributions.get(dependency)
                    if contribution is None:
                        contribution = operation_graph_model.DestructionContribution()
                        contributions[dependency] = contribution
                    # Several separately begun contributions can precede the same
                    # callee Destroy and share a later parent-position Destroy.
                    for operation in contributed_destruction.operations:
                        contribution.operations[operation] = None
                    contribution.first_operations[
                        contributed_destruction.operations[0]
                    ] = None
                    for operation in contributed_destruction.completion_operations:
                        contribution.completion_operations[operation] = None
        return contributions
