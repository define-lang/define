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

import typing
from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    action_contract,
    operation_graph_model,
    operation_graph_rules,
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


def _most_recent_operation_on_position_or_parents(
    last_operations: Mapping[tuple[str, ...], operation_graph_model.LastOperationNode],
    key: tuple[str, ...],
) -> operation_graph_model.LastOperationNode | None:
    """Return the most recent operation on ``key`` or one of its parent names."""
    last_operation: operation_graph_model.LastOperationNode | None = None
    for length in range(len(key), 0, -1):
        operation = last_operations.get(key[:length])
        if operation is not None and (
            last_operation is None
            or last_operation.operation_order < operation.operation_order
        ):
            last_operation = operation
    return last_operation


def _last_operation_on_position_or_parents(
    last_operations: Mapping[tuple[str, ...], operation_graph_model.LastOperationNode],
    key: tuple[str, ...],
) -> operation_graph_model.LastOperationNode:
    """Return the last operation on ``key`` or one of its parent names."""
    last_operation = _most_recent_operation_on_position_or_parents(last_operations, key)
    if last_operation is None:
        raise KeyError(key)
    return last_operation


@typing.final
class _LastOperationsByPosition:
    """Track the last operation recorded on each position."""

    def __init__(self):
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
        # unbounded memory as position depth and breadth grew. Keep the mapping
        # as the exact fallback: valid programs can interleave writes without
        # temporal locality, and any index miss must still return the same result
        # as the complete prefix scan.
        #
        # Every mapping write must go through record so the tuple is an exact
        # suffix of write history. It is searched newest first. A matching
        # retained write is necessarily newer than every evicted write, so it is
        # safe to return immediately; when none matches, the complete mapping
        # scan determines the answer.
        self._recent: tuple[
            tuple[str, ...] | operation_graph_model.LastOperationNode, ...
        ] = ()
        self._by_position: dict[
            tuple[str, ...], operation_graph_model.LastOperationNode
        ] = {}

    def exact(self, key: tuple[str, ...]) -> operation_graph_model.LastOperationNode:
        """Return the last operation recorded on exactly ``key``."""
        return self._by_position[key]

    def get(
        self, key: tuple[str, ...]
    ) -> operation_graph_model.LastOperationNode | None:
        """Return the last operation recorded on exactly ``key``, if any."""
        return self._by_position.get(key)

    def on_position_or_parents(
        self, key: tuple[str, ...]
    ) -> operation_graph_model.LastOperationNode:
        """Return the last operation on ``key`` or one of its parent names."""
        return _last_operation_on_position_or_parents(self._by_position, key)

    def most_recent_on_position_or_parents(
        self, position: tuple[str, ...]
    ) -> operation_graph_model.LastOperationNode | None:
        """Return the most recent operation on a position's parent-name chain."""
        # Check recent writes first to avoid slicing and probing every position
        # prefix. The first match is newer than every omitted write, so it is exact.
        for index in range(len(self._recent) - 2, -1, -2):
            key = typing.cast("tuple[str, ...]", self._recent[index])
            if len(key) <= len(position) and position[: len(key)] == key:
                return typing.cast(
                    "operation_graph_model.LastOperationNode",
                    self._recent[index + 1],
                )
        return _most_recent_operation_on_position_or_parents(
            self._by_position, position
        )

    def body_touched(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly ``key``."""
        node = self._by_position.get(key)
        return node is not None and not isinstance(
            node, operation_graph_model.RequirementNode
        )

    def record(
        self,
        key: tuple[str, ...],
        operation: operation_graph_model.LastOperationNode,
    ):
        """Record the last operation and retain the four most recent writes."""
        self._by_position[key] = operation
        self._recent = (*self._recent[-6:], key, operation)

    def finish(
        self,
    ) -> dict[tuple[str, ...], operation_graph_model.LastOperationNode]:
        """Return the final lookup and discard the construction-only cache."""
        self._recent = ()
        return self._by_position


@typing.final
class OperationGraph:
    """A completed dependency graph of one action's particle operations."""

    def __init__(
        self,
        action: ast.GlobalTypedName,
        *,
        nodes: list[operation_graph_model.OperationNode],
        last_operation: dict[tuple[str, ...], operation_graph_model.LastOperationNode],
        executions: list[operation_graph_model.ActionExecution],
        guaranteed_positions_by_operation: dict[
            operation_graph_model.ConcreteOperationNode,
            tuple[tuple[str, ...], ...],
        ],
        destructions: dict[
            operation_graph_model.DestructionFact,
            operation_graph_model.OperationGraphDestruction,
        ],
        contributed_destruction_fragments_by_direct_callee_execution: dict[
            operation_graph_model.ActionExecution,
            list[operation_graph_model.ContributedDestructionFragment],
        ],
        executions_propagating_destruction_to_caller: set[
            operation_graph_model.ActionExecution
        ],
    ):
        """Initialize a completed Operation Graph."""
        self.action = action
        self._nodes = nodes
        self._last_operation = last_operation
        self._executions = executions
        self.guaranteed_positions_by_operation = guaranteed_positions_by_operation
        self._destructions = destructions
        self._contributed_destruction_fragments_by_direct_callee_execution = (
            contributed_destruction_fragments_by_direct_callee_execution
        )
        self._executions_propagating_destruction_to_caller = (
            executions_propagating_destruction_to_caller
        )

    @property
    def nodes(self) -> Sequence[operation_graph_model.OperationNode]:
        """Every node, in creation order."""
        return self._nodes

    @property
    def particle_operations(
        self,
    ) -> Iterable[operation_graph_model.PositionOperationNode]:
        """Iterate over every Particle Operation in creation order."""
        for node in self._nodes:
            if isinstance(node, operation_graph_model.PositionOperationNode):
                yield node

    def last_operation_on_position_or_parents(
        self, key: tuple[str, ...]
    ) -> (
        operation_graph_model.ConcreteOperationNode
        | operation_graph_model.RequirementNode
    ):
        """Return the last operation on ``key`` or one of its parent names."""
        return _last_operation_on_position_or_parents(self._last_operation, key)

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


@typing.final
class OperationGraphBuilder:
    """Build an append-only dependency graph of one action's particle operations."""

    def __init__(self, action: ast.GlobalTypedName):
        """Create an empty operation graph."""
        self.action: ast.GlobalTypedName = action
        self._nodes: list[operation_graph_model.OperationNode] = []
        self._last_operations_by_position = _LastOperationsByPosition()
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
        self._guaranteed_positions_by_operation: dict[
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

    def body_touched_key(self, key: tuple[str, ...]) -> bool:
        """Return whether the body performed a real operation on exactly this key.

        A recorded RequirementNode stands in for a caller operation, not a
        body operation, so it does not count as the body touching the position.
        """
        return self._last_operations_by_position.body_touched(key)

    def record_requirement(
        self,
        position: ast.PositionReference,
        required_state: action_contract.PositionOccupancyState,
    ):
        """Record the caller operation represented by a position requirement."""
        key = position.canonical_chained_name_tuple
        ancestor = typing.cast(
            "operation_graph_model.RequirementNode | None",
            self._last_operations_by_position.most_recent_on_position_or_parents(
                key[:-1]
            ),
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
        self._last_operations_by_position.record(key, node)

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
            firing_operation = self._last_operations_by_position.on_position_or_parents(
                acting_on_position_key
            )
        else:
            firing_operation = self._last_operations_by_position.exact(
                acting_on_position_key
            )
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
                self._last_operations_by_position.most_recent_on_position_or_parents(
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
            self._last_operations_by_position.most_recent_on_position_or_parents(
                target_key
            ),
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
                operation_graph_rules.empty_rule_dependencies_for(child_operations, ())
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
                            self._last_operations_by_position.most_recent_on_position_or_parents(
                                position_key
                            ),
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
        operation = self._last_operations_by_position.get(caller_position_key)
        if operation is not None:
            return operation
        ancestor_operation = (
            self._last_operations_by_position.most_recent_on_position_or_parents(
                caller_position_key
            )
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
        fill_dependency = (
            self._last_operations_by_position.most_recent_on_position_or_parents(
                fill_position
            )
        )

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
        rule_result = operation_graph_rules.determine_empty_rule_dependencies(
            child_operations,
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
        rule_result = operation_graph_rules.determine_move_rule_dependencies(
            child_operations,
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

    def _add_empty_rule_binding_hole(
        self,
        empty_rule_collection: operation_graph_model.CallerEmptyRuleCollection,
        local_nodes: list[operation_graph_model.ConcreteOperationNode],
    ) -> operation_graph_model.EmptyRuleBindingHoleNode:
        """Add and return the Binding Hole for an unfinished Empty Rule."""
        empty_rule_binding_hole = (
            operation_graph_model.EmptyRuleBindingHole.from_collection(
                empty_rule_collection,
                operation_graph_rules.binding_holes_depended_on_by(local_nodes),
            )
        )
        node = operation_graph_model.EmptyRuleBindingHoleNode(
            node_id=len(self._nodes),
            empty_rule_binding_hole=empty_rule_binding_hole,
            remaining_concrete_nodes=tuple(local_nodes),
        )
        self._nodes.append(node)
        return node

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
        self._last_operations_by_position.record(key, node)
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
        fill_dependency = (
            self._last_operations_by_position.most_recent_on_position_or_parents(
                target_key
            )
        )
        depends_on, partial_move_rule_result = self._move_dependencies(
            source_key,
            child_operations,
            fill_dependency,
            typing.cast(
                "operation_graph_model.LastOperationNode",
                self._last_operations_by_position.most_recent_on_position_or_parents(
                    source_key
                ),
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
        self._last_operations_by_position.record(source_key, node)
        self._last_operations_by_position.record(target_key, node)
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
                    self._last_operations_by_position.most_recent_on_position_or_parents(
                        key
                    ),
                ),
            ),
        )
        self._record_destroy_node(node)
        return node

    def _record_destroy_node(self, node: operation_graph_model.DestroyNode):
        """Add a constructed Destroy operation to this graph."""
        self._nodes.append(node)
        self._last_operations_by_position.record(
            node.target.canonical_chained_name_tuple, node
        )

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
            tuple[tuple[str, ...], ...], operation_graph_model.MoveGuaranteeNode
        ] = {}
        for caller_position, operation_positions_in_guarantee in guaranteed_positions:
            operation_positions = tuple(
                ast.chain_in_caller(guarantee_action_chain, operation_position)
                for operation_position in operation_positions_in_guarantee
            )
            if len(operation_positions) == 2:
                canonical_move_guarantee = canonical_node_by_move_positions.get(
                    operation_positions
                )
                node = operation_graph_model.MoveGuaranteeNode(
                    node_id=len(self._nodes),
                    execution=execution,
                    nested_executions=nested_executions,
                    guaranteed_position=ast.chain_in_callee(
                        operation_graph_action_chain, caller_position
                    ),
                    depends_on=(execution.trigger_operation,),
                    operation_positions=operation_positions,
                    canonical_move_guarantee=canonical_move_guarantee,
                )
                if canonical_move_guarantee is None:
                    canonical_node_by_move_positions[operation_positions] = node
            else:
                node = operation_graph_model.GuaranteeNode(
                    node_id=len(self._nodes),
                    execution=execution,
                    nested_executions=nested_executions,
                    guaranteed_position=ast.chain_in_callee(
                        operation_graph_action_chain, caller_position
                    ),
                    depends_on=(execution.trigger_operation,),
                    operation_positions=operation_positions,
                )
            self._nodes.append(node)
            self._last_operations_by_position.record(caller_position, node)
            nodes[caller_position] = node
        return nodes

    def record_guaranteed_positions(self, positions: Iterable[tuple[str, ...]]):
        """Record guarantees published by this action's Particle Operations."""
        positions_by_operation: dict[
            operation_graph_model.ConcreteOperationNode,
            list[tuple[str, ...]],
        ] = {}
        for position in positions:
            node = self._last_operations_by_position.get(position)
            if not isinstance(
                node,
                (
                    operation_graph_model.PositionOperationNode,
                    operation_graph_model.GuaranteeNode,
                ),
            ):
                continue
            positions_by_operation.setdefault(node, []).append(position)
        self._guaranteed_positions_by_operation = {
            operation: tuple(guaranteed_positions)
            for operation, guaranteed_positions in positions_by_operation.items()
        }

    def finish(self) -> OperationGraph:
        """Finish construction and return the completed Operation Graph."""
        return OperationGraph(
            self.action,
            nodes=self._nodes,
            last_operation=self._last_operations_by_position.finish(),
            executions=self._executions,
            guaranteed_positions_by_operation=self._guaranteed_positions_by_operation,
            destructions=self._destructions,
            contributed_destruction_fragments_by_direct_callee_execution=(
                self._contributed_destruction_fragments_by_direct_callee_execution
            ),
            executions_propagating_destruction_to_caller=(
                self._executions_propagating_destruction_to_caller
            ),
        )


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

    Adding an operation graph while other threads read this collection is not
    supported. Calls from multiple threads write distinct destruction keys,
    while shared guarantee operations are published with CPython's internally
    synchronized dictionary operations.
    """

    def __init__(self):
        """Initialize an empty operation-graph collection."""
        super().__init__()
        self._guarantee_resolutions: dict[
            str, dict[tuple[str, ...], operation_graph_model.PositionOperationNode]
        ] = {}
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
        # The get avoids allocating a candidate dictionary on cache hits;
        # setdefault rechecks and publishes the candidate in one synchronized
        # CPython dictionary operation when independent callers miss together.
        action_resolutions = self._guarantee_resolutions.get(action.full_typed_name)
        if action_resolutions is None:
            action_resolutions = self._guarantee_resolutions.setdefault(
                action.full_typed_name, {}
            )
        operation = action_resolutions.get(position)
        if operation is None:
            candidate = typing.cast(
                "operation_graph_model.PositionOperationNode",
                self[action].last_operation_on_position_or_parents(position),
            )
            operation = action_resolutions.setdefault(position, candidate)
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
