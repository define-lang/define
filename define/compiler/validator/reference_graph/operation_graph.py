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
    from collections.abc import Iterable, Mapping, Sequence


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


@dataclass(frozen=True, slots=True)
class _RecordedContributedPosition:
    """Graph records associated with one contributed position."""

    operation: operation_graph_model.DestructionFragmentDestroyNode
    contributions: list[_RecordedDestructionContribution]


# TODO: Separate Empty and Move Rule application and caller-binding substitution
# from node storage and recording. Keeping all of these responsibilities on
# OperationGraph makes its invariants and API difficult to understand.
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
        )
        self._nodes.append(self._action_parent_last_operation)
        self.guaranteed_positions_by_operation: dict[
            operation_graph_model.ConcreteOperationNode,
            tuple[tuple[str, ...], ...],
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
        operation_graph_model.ConcreteOperationNode
        | operation_graph_model.RequirementNode
    ):
        """Return the last operation recorded on exactly ``key``."""
        return self._last_operation[key]

    def last_operation_on_position_or_parents(
        self, key: tuple[str, ...]
    ) -> (
        operation_graph_model.ConcreteOperationNode
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
            requirement=operation_graph_model.OperationGraphRequirement(
                requirement_position=key,
                required_state=required_state,
            ),
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
        # TODO: Associate each destructor Action Execution with the Destroy operation
        # that fires it. Destructors are currently recorded before that Destroy exists,
        # so a preceding Requirement Node can become trigger_operation and codegen
        # treats satisfying the requirement as the trigger. Once destruction recording
        # exposes the firing Destroy, remove destructor_trigger_requirement and exclude
        # RequirementNode from Action Execution trigger handling.
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
        requirement_satisfactions: dict[
            tuple[str, ...], operation_graph_model.RequirementSatisfaction
        ] = {}
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
        requirement_satisfactions[trigger_position_key] = (
            self._requirement_satisfaction(
                operation_graph_model.ParticleChildOperations.from_preceding_operations(
                    acting_on_preceding_child_operations
                ),
                firing_operation,
            )
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
            satisfying_operation = self._operation_satisfying_requirement(
                caller_position_key
            )
            if satisfying_operation is not None:
                requirement_satisfactions[requirement_key] = (
                    self._requirement_satisfaction(
                        operation_graph_model.ParticleChildOperations.from_preceding_operations(
                            preceding_child_operations
                        ),
                        satisfying_operation,
                    )
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
            requirement_satisfactions=requirement_satisfactions,
            action_parent_last_operation=action_parent_last_operation,
        )
        self._executions.append(execution)
        return execution

    def _requirement_satisfaction(
        self,
        child_operations: operation_graph_model.ParticleChildOperations,
        operation: operation_graph_model.LastOperationNode,
    ) -> operation_graph_model.RequirementSatisfaction:
        """Return the caller dependencies that satisfy a callee requirement."""
        # A move that brought the whole particle here already depends on every
        # older child operation, so retaining them would add redundant edges.
        if isinstance(
            operation, operation_graph_model.MoveNode
        ) and child_operations.all_precede(operation):
            child_operations = operation_graph_model.ParticleChildOperations()
        return operation_graph_model.RequirementSatisfaction(
            operation, child_operations
        )

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
            depends_on=self._destroy_dependencies(
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
        if not newly_occupied_children.children:
            return
        destroyed_particle_key = newly_occupied_children.destroyed_particle_position.canonical_chained_name_tuple
        fragment = self._record_contributed_destruction_operations(
            execution,
            newly_occupied_children,
            destruction,
            destroyed_position_relative_to_fact,
            destroyed_particle_key,
            newly_occupied_children.children,
        )
        self._contributed_destruction_fragments_by_direct_callee_execution.setdefault(
            execution, []
        ).append(fragment)

    def _record_contributed_destruction_operations(
        self,
        execution: operation_graph_model.ActionExecution,
        newly_occupied_children: operation_graph_model.DestructionContractNewlyOccupiedChildren,
        destruction: operation_graph_model.OperationGraphDestruction,
        destroyed_position_relative_to_fact: tuple[str, ...],
        destroyed_particle_key: tuple[str, ...],
        contributed_positions: Sequence[
            operation_graph_model.ContributedDestructionPosition
        ],
    ) -> operation_graph_model.ContributedDestructionFragment:
        destruction_fact = newly_occupied_children.destruction_fact
        # By the Empty Rule, a caller-contributed Destroy depends on the caller's
        # earlier operations on relevant child positions of the destroyed particle.
        # The Action Requirement satisfaction records those operations.
        destroyed_particle_position_in_callee = ast.chain_in_callee(
            execution.action_chain, destroyed_particle_key
        )
        child_operations = execution.requirement_satisfactions[
            destroyed_particle_position_in_callee
        ].child_operations
        contribution_positions: set[tuple[str, ...]] = set()
        for contributed_position in contributed_positions:
            if not contributed_position.preceding_contributed_positions:
                contribution_positions.add(
                    contributed_position.position_relative_to_destroyed_particle
                )
        # Each separate contribution needs only the preceding operations on child
        # positions of the position it destroys. Partition once to avoid searching
        # all retained child operations for every contribution.
        child_operations_by_contribution_position = child_operations.partition_for_child_positions_without_parent_child_relationships(
            contribution_positions
        )
        operations: list[operation_graph_model.DestructionFragmentDestroyNode] = []
        contributions: list[_RecordedDestructionContribution] = []
        # Record which contributions contain each Destroy. When a later
        # parent-position Destroy depends on those child-position Destroys, add the
        # parent-position Destroy to the same contributions.
        records_by_contributed_position: dict[
            operation_graph_model.ContributedDestructionPosition,
            _RecordedContributedPosition,
        ] = {}
        for newly_occupied_child in contributed_positions:
            position = newly_occupied_child.position
            position_key = position.canonical_chained_name_tuple
            callee_destroy_position = (
                *destroyed_position_relative_to_fact,
                *newly_occupied_child.callee_destroy_position_relative_to_destroyed_particle,
            )
            preceding_contributed_positions = (
                newly_occupied_child.preceding_contributed_positions
            )
            # Validation records cascade Destroys child before parent, so these
            # positions always have operations already constructed in this loop.
            local_dependencies: list[
                operation_graph_model.DestructionFragmentDestroyNode
            ] = [
                records_by_contributed_position[contributed_position].operation
                for contributed_position in preceding_contributed_positions
            ]
            operation_contributions: list[_RecordedDestructionContribution] = []
            for contributed_position in preceding_contributed_positions:
                operation_contributions.extend(
                    records_by_contributed_position[contributed_position].contributions
                )
            if local_dependencies:
                # A parent-position Destroy continues the contributions begun by its
                # child-position Destroys rather than beginning another contribution.
                local_dependency_nodes = tuple(local_dependencies)
                dependencies = local_dependency_nodes
                dependencies_before_caller_contribution = local_dependency_nodes
                dependencies_after_caller_contribution = local_dependency_nodes
            else:
                # A caller-known occupied child position with no contributed child
                # Destroy must begin a separate contribution because no existing
                # contribution contains it.
                contribution_position = position_key[len(destroyed_particle_key) :]
                contribution = operation_graph_model.DestructionContributionNode(
                    node_id=len(self._nodes),
                    depends_on=self._destroy_dependencies(
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
                destruction_position=(
                    *destroyed_position_relative_to_fact,
                    *newly_occupied_child.position_relative_to_destroyed_particle,
                ),
                dependencies_before_caller_contribution=dependencies_before_caller_contribution,
                dependencies_after_caller_contribution=dependencies_after_caller_contribution,
                direct_callee_execution=execution,
                target_in_destroying_action=target_in_destroying_action,
            )
            self._nodes.append(operation)
            operations.append(operation)
            records_by_contributed_position[newly_occupied_child] = (
                _RecordedContributedPosition(
                    operation,
                    operation_contributions,
                )
            )
            # When a parent-position Destroy depends on a child-position Destroy,
            # add the parent-position Destroy to every contribution that contains
            # the child-position Destroy.
            for recorded_contribution in operation_contributions:
                recorded_contribution.operations.append(operation)
            destruction.operations_by_position[operation.destruction_position] = (
                operation
            )
        # The final contributed positions have no contributed parent-position
        # Destroy, so each contribution's callee Destroy depends on them.
        for contributed_position in newly_occupied_children.final_contributed_positions:
            record = records_by_contributed_position[contributed_position]
            for recorded_contribution in record.contributions:
                recorded_contribution.completion_operations.append(record.operation)
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
        contribution_dependencies: list[
            operation_graph_model.EmptyRuleDependencyNode
        ] = []
        for contribution in contributions:
            contribution_dependencies.extend(contribution.node.depends_on)
        return operation_graph_model.ContributedDestructionFragment(
            tuple(contribution_dependencies),
            tuple(operations),
            tuple(contributed_destructions),
        )

    def _get_or_create_destruction(
        self,
        destruction_fact: operation_graph_model.DestructionFact,
    ) -> operation_graph_model.OperationGraphDestruction:
        destruction = self._destructions.get(destruction_fact)
        if destruction is None:
            destruction = operation_graph_model.OperationGraphDestruction()
            self._destructions[destruction_fact] = destruction
        return destruction

    def _operation_satisfying_requirement(
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

    def _create_dependency(
        self,
        fill_position: tuple[str, ...],
    ) -> operation_graph_model.ActionParentOperationNode:
        """Return the dependency required before filling one position."""
        # Filling a position waits on the most recent operation on that
        # position and its parent names, so the parent particle is present.
        fill_dependency = self._most_recent_ancestor_chain_operation(fill_position)

        if fill_dependency is not None:
            return fill_dependency
        return self._action_parent_last_operation

    def _destroy_dependencies(
        self,
        target: ast.PositionReference,
        child_operations: operation_graph_model.ParticleChildOperations,
        emptied_ancestor: operation_graph_model.LastOperationNode,
    ) -> tuple[operation_graph_model.EmptyRuleDependencyNode, ...]:
        """Return dependencies required before destroying one particle."""
        key = target.canonical_chained_name_tuple
        rule_result = child_operations.determine_empty_rule_dependencies(
            key,
            emptied_ancestor,
        )
        if rule_result.caller_collection is None:
            return tuple(rule_result.local_nodes)
        return (
            *rule_result.local_nodes,
            self._add_empty_rule_binding_hole(
                rule_result.caller_collection,
                rule_result.local_nodes,
            ),
        )

    def _move_dependencies(
        self,
        empty_position: tuple[str, ...],
        child_operations: operation_graph_model.ParticleChildOperations,
        fill_dependency: operation_graph_model.LastOperationNode | None,
        emptied_ancestor: operation_graph_model.LastOperationNode,
    ) -> tuple[
        tuple[operation_graph_model.ConcreteOperationNode, ...],
        operation_graph_model.PartialMoveRuleResult | None,
    ]:
        """Apply the Move Rule with the known Fill and Empty dependencies."""
        rule_result = child_operations.determine_move_rule_dependencies(
            empty_position,
            fill_dependency,
            emptied_ancestor,
        )
        direct_dependencies = tuple(rule_result.local_nodes)
        remaining_fill_dependency = None
        # A caller-controlled Fill Dependency must remain until it is bound. Keep
        # a concrete Fill Dependency only if the local rule result retained it.
        if isinstance(fill_dependency, operation_graph_model.RequirementNode) or (
            fill_dependency in rule_result.local_nodes
        ):
            remaining_fill_dependency = fill_dependency
        if rule_result.caller_collection is None:
            if rule_result.partial_move_rule_comparison_positions is None:
                # We have a fully-complete Move Rule that can be resolved within
                # this action.
                return direct_dependencies, None
            partial_move_rule_result = operation_graph_model.PartialMoveRuleResultWithCompleteEmptyRuleCollection(
                fill_dependency=remaining_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    rule_result.fill_dependency_is_also_empty_dependency
                ),
                collected_operation_positions=rule_result.partial_move_rule_comparison_positions,
            )
        else:
            partial_move_rule_result = operation_graph_model.PartialMoveRuleResultWithCallerEmptyRuleCollection(
                fill_dependency=remaining_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    rule_result.fill_dependency_is_also_empty_dependency
                ),
                empty_rule_collection=rule_result.caller_collection,
            )
        return (
            direct_dependencies,
            partial_move_rule_result,
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

    def _add_empty_rule_binding_hole(
        self,
        empty_rule_collection: operation_graph_model.CallerEmptyRuleCollection,
        local_nodes: list[operation_graph_model.ConcreteOperationNode],
    ) -> operation_graph_model.EmptyRuleBindingHoleNode:
        """Add and return the Binding Hole for an unfinished Empty Rule."""
        empty_rule_binding_hole = (
            operation_graph_model.EmptyRuleBindingHole.from_collection(
                empty_rule_collection,
                self.binding_holes_depended_on_by(local_nodes),
            )
        )
        node = operation_graph_model.EmptyRuleBindingHoleNode(
            node_id=len(self._nodes),
            empty_rule_binding_hole=empty_rule_binding_hole,
            remaining_concrete_nodes=tuple(local_nodes),
        )
        self._nodes.append(node)
        return node

    def binding_holes_depended_on_by(
        self,
        nodes: Iterable[operation_graph_model.ConcreteOperationNode],
        *,
        caller_binding_holes: Iterable[operation_graph_model.BindingHole] = (),
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[
                operation_graph_model.ConcreteOperationNode
                | operation_graph_model.BindingHole
            ],
        ]
        | None = None,
    ) -> tuple[operation_graph_model.BindingHole, ...]:
        """Return Binding Holes the supplied nodes depend on directly or indirectly.

        The result uses deterministic first-encounter order as a stable tie-break;
        the order gives no semantic priority to one Binding Hole over another.
        """
        prerequisite_binding_holes = list(caller_binding_holes)
        # A prerequisite binding can supply the same Binding Hole that a concrete
        # caller node depends on, so mark directly supplied holes visited.
        visited: set[
            operation_graph_model.OperationNode | operation_graph_model.BindingHole
        ] = set(prerequisite_binding_holes)
        nodes_to_visit: list[
            operation_graph_model.OperationNode | operation_graph_model.BindingHole
        ] = []
        # Walk the dependency tree of the passed-in nodes and extract all binding
        # holes.
        for node in nodes:
            nodes_to_visit.append(node)
            while nodes_to_visit:
                current_node = nodes_to_visit.pop()
                if current_node in visited:
                    continue
                visited.add(current_node)
                if isinstance(
                    current_node,
                    (
                        operation_graph_model.ActionParentLastOperationNode,
                        operation_graph_model.RequirementNode,
                        operation_graph_model.EmptyRuleBindingHoleNode,
                        operation_graph_model.EmptyRuleBindingHole,
                        operation_graph_model.MoveRuleBindingHole,
                    ),
                ):
                    prerequisite_binding_holes.append(current_node)
                    continue
                replacement_depends_on_targets = None
                if replacement_depends_on_targets_by_node is not None:
                    replacement_depends_on_targets = (
                        replacement_depends_on_targets_by_node.get(current_node)
                    )
                if replacement_depends_on_targets is None:
                    nodes_to_visit.extend(reversed(current_node.depends_on))
                else:
                    nodes_to_visit.extend(reversed(replacement_depends_on_targets))
        return tuple(prerequisite_binding_holes)

    def apply_partial_move_rule_result(
        self,
        move: operation_graph_model.MoveNodeWithPartialMoveRuleResult,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[
                operation_graph_model.ConcreteOperationNode
                | operation_graph_model.BindingHole
            ],
        ],
    ) -> tuple[operation_graph_model.MoveRuleApplicationResult, bool]:
        """Finish a partial Move Rule and report whether its depends_on relationships changed."""
        partial_result = move.partial_move_rule_result
        caller_fill_dependency = None
        concrete_fill_dependency = None
        if isinstance(
            partial_result.fill_dependency, operation_graph_model.RequirementNode
        ):
            caller_fill_dependency = operation_graph_model.CallerFillDependency(
                callee_binding_hole=partial_result.fill_dependency,
                requirement=partial_result.fill_dependency.requirement,
            )
        else:
            concrete_fill_dependency = partial_result.fill_dependency

        nodes_remaining_after_comparison = move.depends_on
        nodes_remaining_after_correction = (
            operation_graph_model.apply_move_correction_and_fill_dependency_removal(
                nodes_remaining_after_comparison,
                concrete_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    partial_result.fill_dependency_is_also_empty_dependency
                ),
                replacement_depends_on_targets_by_node=(
                    replacement_depends_on_targets_by_node
                ),
            )
        )
        application_result = self._complete_or_propagate_move_rule(
            nodes_remaining_after_correction,
            caller_empty_rule_collection=partial_result.caller_empty_rule_collection,
            caller_fill_dependency=caller_fill_dependency,
            comparison_positions=partial_result.comparison_positions,
            fill_dependency_is_also_empty_dependency=(
                partial_result.fill_dependency_is_also_empty_dependency
            ),
            caller_binding_holes=(),
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )
        # A remaining Binding Hole changes the Move's relationships. Otherwise,
        # Move Correction preserves the input sequence when it removes nothing,
        # avoiding a second traversal merely to compare the relationships.
        relationships_changed = (
            application_result.move_rule_binding_hole is not None
            or nodes_remaining_after_correction is not nodes_remaining_after_comparison
        )
        return application_result, relationships_changed

    def _complete_or_propagate_move_rule(
        self,
        concrete_caller_nodes: Sequence[operation_graph_model.ConcreteOperationNode],
        *,
        caller_empty_rule_collection: (
            operation_graph_model.CallerEmptyRuleCollection | None
        ),
        caller_fill_dependency: operation_graph_model.CallerFillDependency | None,
        comparison_positions: Sequence[tuple[str, ...]],
        fill_dependency_is_also_empty_dependency: bool,
        caller_binding_holes: Iterable[operation_graph_model.BindingHole],
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[
                operation_graph_model.ConcreteOperationNode
                | operation_graph_model.BindingHole
            ],
        ],
    ) -> operation_graph_model.MoveRuleApplicationResult:
        """Return a complete Move Rule result or its Binding Hole for the next caller."""
        if caller_empty_rule_collection is None and caller_fill_dependency is None:
            return operation_graph_model.MoveRuleApplicationResult(
                concrete_caller_nodes,
                None,
            )
        prerequisite_binding_holes = self.binding_holes_depended_on_by(
            concrete_caller_nodes,
            caller_binding_holes=caller_binding_holes,
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )
        if caller_empty_rule_collection is None:
            move_rule_binding_hole = operation_graph_model.MoveRuleBindingHoleWithCompleteEmptyRuleCollection(
                caller_fill_dependency=caller_fill_dependency,
                fill_dependency_is_also_empty_dependency=(
                    fill_dependency_is_also_empty_dependency
                ),
                prerequisite_binding_holes=prerequisite_binding_holes,
                collected_operation_positions=tuple(comparison_positions),
            )
        else:
            move_rule_binding_hole = (
                operation_graph_model.MoveRuleBindingHoleWithCallerEmptyRuleCollection(
                    caller_fill_dependency=caller_fill_dependency,
                    fill_dependency_is_also_empty_dependency=(
                        fill_dependency_is_also_empty_dependency
                    ),
                    prerequisite_binding_holes=prerequisite_binding_holes,
                    empty_rule_collection=caller_empty_rule_collection,
                )
            )
        return operation_graph_model.MoveRuleApplicationResult(
            concrete_caller_nodes,
            move_rule_binding_hole,
        )

    def _collect_empty_dependencies_from_caller(
        self,
        execution: operation_graph_model.ActionExecution,
        caller_empty_rule_collection: operation_graph_model.CallerEmptyRuleCollection,
    ) -> tuple[
        set[operation_graph_model.LastOperationNode],
        tuple[str, ...] | None,
        set[tuple[str, ...]],
    ]:
        """Collect the remaining Empty Dependencies from one direct caller."""
        particle_requirement_satisfaction = execution.requirement_satisfactions[
            caller_empty_rule_collection.requirement_position
        ]
        child_operations = particle_requirement_satisfaction.child_operations.operations_not_on_same_paths_as(
            caller_empty_rule_collection.collected_child_operation_positions
        )
        collected_nodes: set[operation_graph_model.LastOperationNode] = {
            child_operation.operation for child_operation in child_operations
        }
        fill_dependency_requirement_position = (
            caller_empty_rule_collection.fill_dependency_requirement_position
        )
        if fill_dependency_requirement_position is not None:
            # The Fill Rule allows an EMPTY requirement to depend on an
            # operation on any parent position. Search the required position
            # and its parent-position prefixes for that operation.
            for depth in range(len(fill_dependency_requirement_position), 0, -1):
                callee_requirement_position = fill_dependency_requirement_position[
                    :depth
                ]
                requirement_satisfaction = execution.requirement_satisfactions.get(
                    callee_requirement_position
                )
                if requirement_satisfaction is None:
                    continue
                # The Move Rule combines the Empty Dependencies for the source
                # position with the Fill Dependency for the target position, then
                # applies Comparison. When the Fill Dependency operates on a
                # transitive parent position of the source, a more recent Particle
                # Operation on the source or one of its transitive child positions
                # remains after Comparison.
                if not ast.is_prefix(
                    callee_requirement_position,
                    caller_empty_rule_collection.requirement_position,
                ):
                    collected_nodes.add(requirement_satisfaction.operation)
                break

        requirement_position_in_caller = self._occupied_requirement_position(
            particle_requirement_satisfaction
        )
        # The particle is not from an earlier caller, so Collection is complete
        # after adding the operation that supplied it when no child operation did.
        if requirement_position_in_caller is None and (
            not child_operations
            and not caller_empty_rule_collection.collected_child_operation_positions
        ):
            collected_nodes.add(particle_requirement_satisfaction.operation)

        collected_child_operation_positions: set[tuple[str, ...]] = set()
        if requirement_position_in_caller is not None:
            collected_child_operation_positions.update(
                child_operation.child_position
                for child_operation in particle_requirement_satisfaction.child_operations.operations
            )
            collected_child_operation_positions.update(
                caller_empty_rule_collection.collected_child_operation_positions
            )
        return (
            collected_nodes,
            requirement_position_in_caller,
            collected_child_operation_positions,
        )

    def apply_empty_rule_binding_hole_in_caller(
        self,
        execution: operation_graph_model.ActionExecution,
        empty_rule_binding_hole: operation_graph_model.EmptyRuleBindingHole,
        empty_rule_binding_inputs: operation_graph_model.EmptyRuleBindingInputs,
        *,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[
                operation_graph_model.ConcreteOperationNode
                | operation_graph_model.BindingHole
            ],
        ]
        | None = None,
    ) -> operation_graph_model.EmptyRuleApplicationResult:
        """Bind the callee's Empty Rule Binding Hole in one direct caller."""
        (
            collected_nodes,
            requirement_position_in_caller,
            collected_child_operation_positions,
        ) = self._collect_empty_dependencies_from_caller(
            execution,
            empty_rule_binding_hole,
        )

        collected_operation_positions = [
            ast.chain_in_caller(execution.action_chain, position)
            for position in empty_rule_binding_hole.collected_operation_positions
        ]
        (
            caller_nodes,
            collected_nodes_most_recent_first,
        ) = operation_graph_model.apply_empty_rule_to_caller_collection(
            collected_nodes,
            collected_operation_positions,
            empty_rule_binding_inputs.concrete_caller_nodes,
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )
        if requirement_position_in_caller is None:
            return operation_graph_model.EmptyRuleApplicationResult(
                caller_nodes,
                None,
            )

        caller_nodes_for_next_substitution: list[
            operation_graph_model.ConcreteOperationNode
        ] = []
        fill_dependency_requirement_position: tuple[str, ...] | None = None
        for node in caller_nodes:
            if isinstance(node, operation_graph_model.RequirementNode):
                fill_dependency_requirement_position = (
                    node.requirement.requirement_position
                )
                continue
            caller_nodes_for_next_substitution.append(node)
            # This remains linear in the operated positions because each position
            # is examined once, without comparing nodes.
            self._add_positions_relative_to_particle(
                collected_child_operation_positions,
                node,
                requirement_position_in_caller,
            )

        for node in reversed(collected_nodes_most_recent_first):
            collected_operation_positions.extend(node.operated_positions)
        prerequisite_binding_holes = self.binding_holes_depended_on_by(
            (
                *empty_rule_binding_inputs.concrete_caller_nodes,
                *caller_nodes_for_next_substitution,
            ),
            caller_binding_holes=empty_rule_binding_inputs.caller_binding_holes,
        )
        return operation_graph_model.EmptyRuleApplicationResult(
            # TODO: Remove this cast when EmptyRuleApplicationResult is split into
            # complete and continuing variants. The continuing variant can type
            # caller_nodes as list[ConcreteOperationNode].
            typing.cast(
                "list[operation_graph_model.LastOperationNode]",
                caller_nodes_for_next_substitution,
            ),
            operation_graph_model.EmptyRuleBindingHole(
                requirement_position=requirement_position_in_caller,
                collected_child_operation_positions=frozenset(
                    collected_child_operation_positions
                ),
                fill_dependency_requirement_position=(
                    fill_dependency_requirement_position
                ),
                collected_operation_positions=tuple(collected_operation_positions),
                prerequisite_binding_holes=prerequisite_binding_holes,
            ),
        )

    def apply_move_rule_binding_hole_in_caller(
        self,
        execution: operation_graph_model.ActionExecution,
        move_rule_binding_hole: operation_graph_model.MoveRuleBindingHole,
        empty_rule_binding_inputs: operation_graph_model.EmptyRuleBindingInputs,
        *,
        replacement_depends_on_targets_by_node: Mapping[
            operation_graph_model.OperationNode,
            Sequence[
                operation_graph_model.ConcreteOperationNode
                | operation_graph_model.BindingHole
            ],
        ],
    ) -> operation_graph_model.MoveRuleApplicationResult:
        """Apply a callee Move Rule Binding Hole using one direct caller."""
        caller_empty_rule_collection = (
            move_rule_binding_hole.caller_empty_rule_collection
        )
        if caller_empty_rule_collection is None:
            collected_nodes: set[operation_graph_model.ConcreteOperationNode] = set()
            requirement_position_in_caller = None
            collected_child_operation_positions: set[tuple[str, ...]] = set()
        else:
            (
                collected_empty_dependencies,
                requirement_position_in_caller,
                collected_child_operation_positions,
            ) = self._collect_empty_dependencies_from_caller(
                execution,
                caller_empty_rule_collection,
            )
            collected_nodes = typing.cast(
                "set[operation_graph_model.ConcreteOperationNode]",
                collected_empty_dependencies,
            )

        fill_dependency = move_rule_binding_hole.caller_fill_dependency
        if fill_dependency is not None:
            fill_dependency = execution.resolve_move_rule_fill_dependency(
                fill_dependency
            )
        match fill_dependency:
            case (
                operation_graph_model.PositionOperationNode()
                | operation_graph_model.GuaranteeNode()
            ):
                concrete_fill_dependency = fill_dependency
                caller_fill_dependency = None
            case operation_graph_model.CallerFillDependency() | None:
                concrete_fill_dependency = None
                caller_fill_dependency = fill_dependency

        comparison_positions = [
            ast.chain_in_caller(execution.action_chain, position)
            for position in move_rule_binding_hole.comparison_positions
        ]
        (
            concrete_caller_nodes,
            collected_nodes_most_recent_first,
        ) = operation_graph_model.apply_move_rule_to_caller_collection(
            collected_nodes,
            comparison_positions,
            concrete_fill_dependency,
            empty_rule_binding_inputs.concrete_caller_nodes,
            fill_dependency_is_also_empty_dependency=(
                move_rule_binding_hole.fill_dependency_is_also_empty_dependency
            ),
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )
        next_caller_empty_rule_collection = None
        if (
            requirement_position_in_caller is not None
            or caller_fill_dependency is not None
        ):
            for node in reversed(collected_nodes_most_recent_first):
                comparison_positions.extend(node.operated_positions)
            if requirement_position_in_caller is not None:
                for node in concrete_caller_nodes:
                    self._add_positions_relative_to_particle(
                        collected_child_operation_positions,
                        node,
                        requirement_position_in_caller,
                    )
                next_caller_empty_rule_collection = (
                    operation_graph_model.CallerEmptyRuleCollection(
                        requirement_position=requirement_position_in_caller,
                        collected_child_operation_positions=frozenset(
                            collected_child_operation_positions
                        ),
                        fill_dependency_requirement_position=None,
                        collected_operation_positions=tuple(comparison_positions),
                    )
                )
        return self._complete_or_propagate_move_rule(
            concrete_caller_nodes,
            caller_empty_rule_collection=next_caller_empty_rule_collection,
            caller_fill_dependency=caller_fill_dependency,
            comparison_positions=comparison_positions,
            fill_dependency_is_also_empty_dependency=(
                move_rule_binding_hole.fill_dependency_is_also_empty_dependency
            ),
            caller_binding_holes=empty_rule_binding_inputs.caller_binding_holes,
            replacement_depends_on_targets_by_node=(
                replacement_depends_on_targets_by_node
            ),
        )

    @staticmethod
    def _occupied_requirement_position(
        requirement_satisfaction: operation_graph_model.RequirementSatisfaction,
    ) -> tuple[str, ...] | None:
        if not isinstance(
            requirement_satisfaction.operation,
            operation_graph_model.RequirementNode,
        ):
            return None
        return requirement_satisfaction.operation.requirement.requirement_position

    @staticmethod
    def _add_positions_relative_to_particle(
        relative_positions: set[tuple[str, ...]],
        node: operation_graph_model.ConcreteOperationNode,
        particle_position: tuple[str, ...],
    ):
        for position in node.operated_positions:
            if not ast.is_prefix(particle_position, position):
                continue
            relative_positions.add(position[len(particle_position) :])

    def record_create(
        self, target: ast.PositionReference
    ) -> operation_graph_model.CreateNode:
        """Record a body create in ``target``."""
        key = target.canonical_chained_name_tuple
        dependency = self._create_dependency(key)
        node = operation_graph_model.CreateNode(
            node_id=len(self._nodes),
            target=target,
            depends_on=(dependency,),
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
        fill_dependency = self._most_recent_ancestor_chain_operation(target_key)
        depends_on, partial_move_rule_result = self._move_dependencies(
            source_key,
            child_operations,
            fill_dependency,
            typing.cast(
                "operation_graph_model.LastOperationNode",
                self._most_recent_ancestor_chain_operation(source_key),
            ),
        )
        if partial_move_rule_result is None:
            node = operation_graph_model.MoveNode(
                node_id=len(self._nodes),
                target=target,
                source=source,
                depends_on=depends_on,
            )
        else:
            node = operation_graph_model.MoveNodeWithPartialMoveRuleResult(
                node_id=len(self._nodes),
                target=target,
                source=source,
                depends_on=depends_on,
                partial_move_rule_result=partial_move_rule_result,
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
            depends_on=self._destroy_dependencies(
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
        canonical_node_by_move_positions: dict[
            tuple[tuple[str, ...], ...], operation_graph_model.GuaranteeNode
        ] = {}
        for caller_position, operation_positions_in_guarantee in guaranteed_positions:
            operation_positions = tuple(
                ast.chain_in_caller(guarantee_action_chain, operation_position)
                for operation_position in operation_positions_in_guarantee
            )
            particle_operation_is_move = len(operation_positions) == 2
            canonical_node_for_particle_operation = None
            if particle_operation_is_move:
                canonical_node_for_particle_operation = (
                    canonical_node_by_move_positions.get(operation_positions)
                )
            node = operation_graph_model.GuaranteeNode(
                node_id=len(self._nodes),
                execution=execution,
                nested_executions=nested_executions,
                guaranteed_position=ast.chain_in_callee(
                    operation_graph_action_chain, caller_position
                ),
                depends_on=(execution.trigger_operation,),
                operation_positions=operation_positions,
                _canonical_node_for_particle_operation=(
                    canonical_node_for_particle_operation
                ),
            )
            self._nodes.append(node)
            if (
                particle_operation_is_move
                and canonical_node_for_particle_operation is None
            ):
                canonical_node_by_move_positions[operation_positions] = node
            self._set_last_operation(caller_position, node)
            nodes[caller_position] = node
        return nodes

    def record_guaranteed_positions(self, positions: Iterable[tuple[str, ...]]):
        """Record guarantees published by this action's Particle Operations."""
        positions_by_operation: dict[
            operation_graph_model.ConcreteOperationNode,
            list[tuple[str, ...]],
        ] = {}
        for position in positions:
            node = self._last_operation.get(position)
            if not isinstance(
                node,
                (
                    operation_graph_model.PositionOperationNode,
                    operation_graph_model.GuaranteeNode,
                ),
            ):
                continue
            positions_by_operation.setdefault(node, []).append(position)
        self.guaranteed_positions_by_operation = {
            operation: tuple(guaranteed_positions)
            for operation, guaranteed_positions in positions_by_operation.items()
        }


@dataclass(slots=True)
class GuaranteePath:
    """Action Executions from a guarantee to its publishing Particle Operation."""

    guarantee: operation_graph_model.GuaranteeNode
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
        return GuaranteePath(guarantee, executions, operation)

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
