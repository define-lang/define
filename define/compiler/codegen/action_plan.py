"""DLP 44 lowering for action code generation.

The responsibility of actual codegen renderers should be little more than
translating what's in this plan into names and structures appropriate for
a particular programming language.

The primary purpose of this module is to take in actions where the operation
dependency relationships of the direct callees have been fully resolved and
turn those actions into fragment. A fragment is an independent set of
straight-line operations that have only single, linear dependencies on each
other (basically, one single function that can run synchronously). The
planner then also provides the information needed to render these fragments
into code, such as join requirements and which fragments call each other.

It also provides other data structures that codegen will need in order to
actually render an action, such as information about which guarantees an
action provides, in the exact form that codegen needs in order to render
those guarantees into generated code.

All of these different constructs and their relationships form into
ActionPlan, which is the primary output of this module.

In general, codegen is responsible for language-specific details, and the
action planner (and the code below it) is responsible for language-indepndent
logical representations of what we intend to render.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from define.compiler import ast


# TODO: Trace the complete dataflow from an Operation Graph through every stage
# of codegen—including resolution, action planning, naming, context construction,
# and template rendering—all the way to the final generated source. The purpose
# of the whole pipeline is to perform that transformation, so streamline the
# dataflow across its existing stages to provide the clearest and simplest path
# from the Operation Graph to generated source. Remove intermediate shapes that
# exist only for a later stage to reconstruct the same data or relationships.
@dataclass(slots=True, eq=False)
class ActionFragment:
    """A maximal direct-call chain of Particle Operations."""

    operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath] = field(
        init=False, default_factory=list
    )
    guarantee_publications: list[GuaranteePublication] = field(
        init=False, default_factory=list
    )
    successor_fragments: list[ActionFragment] = field(init=False, default_factory=list)
    callee_binding_joins_that_depend_on_fragment: list[CalleeBindingJoin] = field(
        init=False, default_factory=list
    )
    action_execution_successors: list[operation_graph_model.ActionExecution] = field(
        init=False, default_factory=list
    )
    triggered_action_execution_callee_binding_joins: list[CalleeBindingJoin] = field(
        init=False, default_factory=list
    )
    destruction_connections_to_complete: list[DestructionConnection] = field(
        init=False, default_factory=list
    )
    dependency_count: int = field(init=False, default=0)


@dataclass(slots=True, eq=False)
class DestructionActionFragment(ActionFragment):
    """An Action Fragment that requires a destruction continuation.

    The distinct type lets consumers identify these fragments and access their
    Destruction Fact Destroy without giving every ActionFragment an optional
    destruction operation that cannot exist for ordinary fragments.
    """

    @property
    def destruction_operation(
        self,
    ) -> operation_graph_model.DestructionFactDestroyNode:
        """Return the propagated Destruction Fact Destroy starting this fragment."""
        return typing.cast(
            "operation_graph_model.DestructionFactDestroyNode", self.operations[0]
        )


@dataclass(slots=True, eq=False)
class DestructionConnection:
    """One caller-contributed fragment connected before a direct callee Destroy."""

    callee_destroy: operation_graph_model.DestructionOperation
    operations: Collection[operation_graph_model.DestructionFragmentDestroyNode]
    first_fragments_of_destructions: list[ActionFragment]
    completion_fragments: list[ActionFragment]


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class ActionExecutionPlan:
    """One direct Action Execution and its destruction-connection behavior."""

    execution: operation_graph_model.ActionExecution
    created_destruction_connections: list[DestructionConnection]
    forwards_destruction_connections: bool


@dataclass(frozen=True, slots=True, eq=False)
class BindingHoleFanout:
    """The Action Plan consumers for one Binding Hole."""

    binding_hole: operation_graph_model.BindingHole
    fragments: list[ActionFragment] = field(init=False, default_factory=list)
    callee_binding_joins: list[CalleeBindingJoin] = field(
        init=False, default_factory=list
    )
    destructor_executions: list[operation_graph_model.ActionExecution] = field(
        init=False, default_factory=list
    )


@dataclass(slots=True, eq=False)
class CalleeBindingJoin:
    """The join that completes one direct callee binding."""

    execution: operation_graph_model.ActionExecution
    callee_binding_hole: operation_graph_model.BindingHole
    contributed_destruction_operations: list[
        operation_graph_model.DestructionFragmentDestroyNode
    ]
    guarantee_dependencies: list[operation_graph.GuaranteePath]
    dependency_count: int


type _CalleeBindingJoinsByCalleeBinding = dict[
    operation_graph_action_resolver.CalleeBinding,
    CalleeBindingJoin,
]


@dataclass(frozen=True, slots=True, eq=False)
class GuaranteePublication:
    """Source and target guarantees published by one local Particle Operation."""

    operation: operation_graph_model.PositionOperationNode
    guaranteed_source: tuple[str, ...] | None
    guaranteed_target: tuple[str, ...] | None


@dataclass(frozen=True, slots=True, eq=False)
class TriggerForDestroyedCalleeGuaranteeParticle:
    """An Action Execution for a destroyed callee-guaranteed particle."""

    execution: operation_graph_model.ActionExecution
    guarantee_dependency: operation_graph.GuaranteePath
    callee_binding_joins: list[CalleeBindingJoin]


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """A split representation of an action at one compilation boundary."""

    fragments: list[ActionFragment]
    execute_fragments: list[ActionFragment]
    binding_hole_fanouts: list[BindingHoleFanout]
    action_executions: list[ActionExecutionPlan]
    callee_binding_joins: list[CalleeBindingJoin]
    triggers_for_destroyed_callee_guarantee_particles: list[
        TriggerForDestroyedCalleeGuaranteeParticle
    ]
    guarantee_publications: list[GuaranteePublication]
    accepts_destruction_connections: bool
    destruction_connection_by_operation: dict[
        operation_graph_model.DestructionFragmentDestroyNode,
        DestructionConnection,
    ]


@dataclass(slots=True)
class _FragmentTopology:
    """The fragment structure of one action before its Action Plan is assembled.

    Each fragment is a maximal serial chain of Particle Operations. The topology
    records the Particle Operations in each fragment and the connections between
    fragments.
    """

    fragments: list[ActionFragment]
    fragment_for_operation: dict[
        operation_graph_model.PositionOperationNode, ActionFragment
    ]


@typing.final
class _FragmentTopologyBuilder:
    """Partition one action's Particle Operations into code-generation fragments.

    A fragment ends where a direct method call would not preserve fan-out, a
    join, an Action Execution, guarantee publication, or a dependency supplied
    by the caller.
    """

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        *,
        publishes_guarantees: bool,
        uses_binding_hole_fanouts: bool,
    ):
        self._resolved_action = resolved_action
        self._operations = resolved_action.operations
        self._publishes_guarantees = publishes_guarantees
        self._uses_binding_hole_fanouts = uses_binding_hole_fanouts

    def build(self) -> _FragmentTopology:
        local_successors = self._build_local_successors()
        fragments = self._build_fragments(local_successors)
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ] = {}
        for fragment in fragments:
            for operation in fragment.operations:
                fragment_for_operation[operation] = fragment
        for fragment in fragments:
            fragment.successor_fragments = [
                fragment_for_operation[successor]
                for successor in local_successors[fragment.operations[-1]]
            ]
        return _FragmentTopology(
            fragments,
            fragment_for_operation,
        )

    def _build_local_successors(
        self,
    ) -> dict[
        operation_graph_model.PositionOperationNode,
        list[operation_graph_model.PositionOperationNode],
    ]:
        local_successors: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ] = {operation: [] for operation in self._operations}
        for operation, resolved_operation in self._operations.items():
            for predecessor in resolved_operation.dependencies.local_operations:
                local_successors[predecessor].append(operation)
        return local_successors

    def _build_fragment(
        self, operations: list[operation_graph_model.PositionOperationNode]
    ) -> ActionFragment:
        if self._is_propagated_destruction_operation(operations[0]):
            return DestructionActionFragment(operations)
        return ActionFragment(operations)

    def _build_fragments(
        self,
        local_successors: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ],
    ) -> list[ActionFragment]:
        fragments: list[ActionFragment] = []
        for head in self._operations:
            if self._can_follow_predecessor(head, local_successors):
                continue
            chain = [head]
            while True:
                successors = local_successors[chain[-1]]
                if len(successors) != 1:
                    break
                successor = successors[0]
                if not self._can_follow_predecessor(successor, local_successors):
                    break
                chain.append(successor)
            fragments.append(self._build_fragment(chain))
        return fragments

    def _can_follow_predecessor(
        self,
        operation: operation_graph_model.PositionOperationNode,
        local_successors: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ],
    ) -> bool:
        resolved_operation = self._operations[operation]
        predecessors = resolved_operation.dependencies.local_operations
        if len(predecessors) != 1:
            return False
        if (
            (
                self._uses_binding_hole_fanouts
                and resolved_operation.binding_holes_depended_on
            )
            or self._is_propagated_destruction_operation(operation)
            or (
                isinstance(
                    resolved_operation,
                    operation_graph_action_resolver.ResolvedDestructionOperation,
                )
                and resolved_operation.destruction_dependencies
            )
            or resolved_operation.dependencies.guarantee_dependencies
        ):
            return False
        predecessor = predecessors[0]
        return len(local_successors[predecessor]) == 1 and not self._must_end_fragment(
            predecessor
        )

    def _is_propagated_destruction_operation(
        self, operation: operation_graph_model.PositionOperationNode
    ) -> bool:
        resolved_operation = self._operations[operation]
        if not isinstance(
            resolved_operation,
            operation_graph_action_resolver.ResolvedDestructionOperation,
        ):
            return False
        destruction = self._resolved_action.graph.destruction_for_fact(
            resolved_operation.operation.destruction_fact
        )
        return destruction.is_propagated_to_caller

    def _must_end_fragment(
        self, operation: operation_graph_model.PositionOperationNode
    ) -> bool:
        resolved_operation = self._operations[operation]
        return bool(
            (
                self._publishes_guarantees
                and operation
                in self._resolved_action.graph.guaranteed_positions_by_operation
            )
            or resolved_operation.dependent_callee_bindings
            or resolved_operation.action_executions
        )


@typing.final
class _ActionPlanBuilder:
    """Build code-generation plans from one action operation graph."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
    ):
        """Initialize for one action and its validated operation graph."""
        self._resolved_action = resolved_action

    def build_executed_action(self) -> ActionPlan:
        """Build a plan started directly through the action's execute method."""
        return self._build(
            [],
            publishes_guarantees=False,
            start_directly=True,
        )

    def build_triggered_action(self) -> ActionPlan:
        """Build the reusable Binding Hole plan for this action's callers."""
        return self._build(
            self._resolved_action.binding_holes.with_runtime_consumers,
            publishes_guarantees=True,
            start_directly=False,
        )

    def _build(
        self,
        binding_holes: Sequence[operation_graph_model.BindingHole],
        *,
        publishes_guarantees: bool,
        start_directly: bool,
    ) -> ActionPlan:
        topology = _FragmentTopologyBuilder(
            self._resolved_action,
            publishes_guarantees=publishes_guarantees,
            uses_binding_hole_fanouts=not start_directly,
        ).build()
        (
            action_executions,
            destruction_connection_by_operation,
        ) = self._plan_action_executions(topology)
        callee_binding_join_by_callee_binding = self._plan_callee_binding_joins(
            topology.fragment_for_operation,
            binding_holes,
        )
        guarantee_publications = self._plan_guarantee_publications(
            topology.fragment_for_operation,
            publishes_guarantees=publishes_guarantees,
        )
        self._plan_fragments(topology)
        binding_hole_fanouts = self._plan_binding_hole_fanouts(
            binding_holes,
            topology.fragment_for_operation,
            callee_binding_join_by_callee_binding,
        )
        execute_fragments: list[ActionFragment] = []
        if start_directly:
            for fragment in topology.fragments:
                if fragment.dependency_count == 0:
                    execute_fragments.append(fragment)
        return ActionPlan(
            fragments=topology.fragments,
            execute_fragments=execute_fragments,
            binding_hole_fanouts=binding_hole_fanouts,
            action_executions=action_executions,
            callee_binding_joins=list(callee_binding_join_by_callee_binding.values()),
            triggers_for_destroyed_callee_guarantee_particles=(
                self._plan_triggers_for_destroyed_callee_guarantee_particles(
                    callee_binding_join_by_callee_binding
                )
            ),
            guarantee_publications=guarantee_publications,
            accepts_destruction_connections=(
                self._resolved_action.graph.propagates_destruction_facts
            ),
            destruction_connection_by_operation=destruction_connection_by_operation,
        )

    def _plan_action_executions(
        self,
        topology: _FragmentTopology,
    ) -> tuple[
        list[ActionExecutionPlan],
        dict[
            operation_graph_model.DestructionFragmentDestroyNode,
            DestructionConnection,
        ],
    ]:
        action_executions: list[ActionExecutionPlan] = []
        action_execution_by_execution: dict[
            operation_graph_model.ActionExecution,
            ActionExecutionPlan,
        ] = {}
        for resolved_execution in self._resolved_action.action_executions:
            planned_execution = ActionExecutionPlan(
                execution=resolved_execution.execution,
                created_destruction_connections=[],
                forwards_destruction_connections=(
                    resolved_execution.forwards_destruction_connections
                ),
            )
            action_executions.append(planned_execution)
            action_execution_by_execution[resolved_execution.execution] = (
                planned_execution
            )
        destruction_connection_by_operation: dict[
            operation_graph_model.DestructionFragmentDestroyNode,
            DestructionConnection,
        ] = {}
        for (
            destruction_dependency,
            contribution,
        ) in self._resolved_action.destruction_contributions.items():
            first_fragments_of_destructions = [
                topology.fragment_for_operation[operation]
                for operation in contribution.first_operations
            ]
            completion_fragments = [
                topology.fragment_for_operation[operation]
                for operation in contribution.completion_operations
            ]
            connection = DestructionConnection(
                destruction_dependency.callee_destroy,
                contribution.operations,
                first_fragments_of_destructions,
                completion_fragments,
            )
            action_execution_by_execution[
                destruction_dependency.execution
            ].created_destruction_connections.append(connection)
            for fragment in completion_fragments:
                fragment.destruction_connections_to_complete.append(connection)
            for operation in connection.operations:
                destruction_connection_by_operation[operation] = connection
        return action_executions, destruction_connection_by_operation

    def _plan_callee_binding_joins(
        self,
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ],
        binding_holes: Sequence[operation_graph_model.BindingHole],
    ) -> _CalleeBindingJoinsByCalleeBinding:
        callee_binding_join_by_callee_binding: _CalleeBindingJoinsByCalleeBinding = {}
        for resolved_action_execution in self._resolved_action.action_executions:
            action_execution = resolved_action_execution.execution
            for (
                callee_binding
            ) in resolved_action_execution.callee_bindings.with_runtime_consumers:
                dependencies = callee_binding.caller_dependencies
                dependency_count = (
                    len(dependencies.local_operations)
                    + len(dependencies.guarantee_dependencies)
                    + 1
                )
                # The entry point action has no Binding Holes to contribute.
                if binding_holes:
                    dependency_count += len(callee_binding.caller_binding_holes)
                callee_binding_join = CalleeBindingJoin(
                    execution=action_execution,
                    callee_binding_hole=callee_binding.callee_binding_hole,
                    contributed_destruction_operations=(
                        callee_binding.contributed_destruction_operations
                    ),
                    guarantee_dependencies=dependencies.guarantee_dependencies,
                    dependency_count=dependency_count,
                )
                callee_binding_join_by_callee_binding[callee_binding] = (
                    callee_binding_join
                )
        for resolved_operation in self._resolved_action.operations.values():
            fragment = fragment_for_operation[resolved_operation.operation]
            for callee_binding in resolved_operation.dependent_callee_bindings:
                fragment.callee_binding_joins_that_depend_on_fragment.append(
                    callee_binding_join_by_callee_binding[callee_binding]
                )
            for resolved_action_execution in resolved_operation.action_executions:
                fragment.action_execution_successors.append(
                    resolved_action_execution.execution
                )
                fragment.triggered_action_execution_callee_binding_joins.extend(
                    callee_binding_join_by_callee_binding[callee_binding]
                    for callee_binding in (
                        resolved_action_execution.callee_bindings.with_runtime_consumers
                    )
                )
        return callee_binding_join_by_callee_binding

    def _plan_triggers_for_destroyed_callee_guarantee_particles(
        self,
        callee_binding_join_by_callee_binding: _CalleeBindingJoinsByCalleeBinding,
    ) -> list[TriggerForDestroyedCalleeGuaranteeParticle]:
        triggers: list[TriggerForDestroyedCalleeGuaranteeParticle] = []
        for resolved_action_execution in self._resolved_action.action_executions:
            guarantee_dependency = resolved_action_execution.guarantee_dependency
            if guarantee_dependency is None:
                continue
            callee_binding_joins: list[CalleeBindingJoin] = []
            for (
                callee_binding
            ) in resolved_action_execution.callee_bindings.with_runtime_consumers:
                callee_binding_joins.append(
                    callee_binding_join_by_callee_binding[callee_binding]
                )
            triggers.append(
                TriggerForDestroyedCalleeGuaranteeParticle(
                    execution=resolved_action_execution.execution,
                    guarantee_dependency=guarantee_dependency,
                    callee_binding_joins=callee_binding_joins,
                )
            )
        return triggers

    def _plan_guarantee_publications(
        self,
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ],
        *,
        publishes_guarantees: bool,
    ) -> list[GuaranteePublication]:
        if not publishes_guarantees:
            return []
        publications: list[GuaranteePublication] = []
        for (
            operation,
            publication_positions,
        ) in self._resolved_action.graph.guaranteed_positions_by_operation.items():
            if isinstance(operation, operation_graph_model.GuaranteeNode):
                continue
            guaranteed_source = None
            if isinstance(operation, operation_graph_model.MoveNode):
                source = operation.source.canonical_chained_name_tuple
                if source in publication_positions:
                    guaranteed_source = source
            target = operation.target.canonical_chained_name_tuple
            publication = GuaranteePublication(
                operation=operation,
                guaranteed_source=guaranteed_source,
                guaranteed_target=(target if target in publication_positions else None),
            )
            publications.append(publication)
            fragment_for_operation[operation].guarantee_publications.append(publication)
        return publications

    def _plan_fragments(self, topology: _FragmentTopology):
        for fragment in topology.fragments:
            first_resolved_operation = self._resolved_action.operations[
                fragment.operations[0]
            ]
            first_dependencies = first_resolved_operation.dependencies
            fragment.guarantee_dependencies = first_dependencies.guarantee_dependencies
            destruction_dependency_count = 0
            if isinstance(
                first_resolved_operation,
                operation_graph_action_resolver.ResolvedDestructionOperation,
            ):
                destruction_dependency_count = len(
                    first_resolved_operation.destruction_dependencies
                )
            fragment.dependency_count = (
                len(first_dependencies.local_operations)
                + len(fragment.guarantee_dependencies)
                + destruction_dependency_count
            )

    def _plan_binding_hole_fanouts(
        self,
        binding_holes: Sequence[operation_graph_model.BindingHole],
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ],
        callee_binding_join_by_callee_binding: _CalleeBindingJoinsByCalleeBinding,
    ) -> list[BindingHoleFanout]:
        if not binding_holes:
            return []
        binding_hole_fanouts: list[BindingHoleFanout] = []
        for binding_hole in binding_holes:
            binding_hole_fanouts.append(BindingHoleFanout(binding_hole))
        binding_hole_fanout_by_binding_hole = {
            binding_hole_fanout.binding_hole: binding_hole_fanout
            for binding_hole_fanout in binding_hole_fanouts
        }
        for resolved_operation in self._resolved_action.operations.values():
            fragment = fragment_for_operation[resolved_operation.operation]
            for binding_hole in resolved_operation.binding_holes_depended_on:
                binding_hole_fanout_by_binding_hole[binding_hole].fragments.append(
                    fragment
                )
                fragment.dependency_count += 1
        for resolved_action_execution in self._resolved_action.action_executions:
            for (
                callee_binding
            ) in resolved_action_execution.callee_bindings.with_runtime_consumers:
                callee_binding_join = callee_binding_join_by_callee_binding[
                    callee_binding
                ]
                for binding_hole in callee_binding.caller_binding_holes:
                    binding_hole_fanout_by_binding_hole[
                        binding_hole
                    ].callee_binding_joins.append(callee_binding_join)
            destructor_trigger_requirement = (
                resolved_action_execution.execution.destructor_trigger_requirement
            )
            if destructor_trigger_requirement is not None:
                binding_hole_fanout = binding_hole_fanout_by_binding_hole[
                    destructor_trigger_requirement
                ]
                binding_hole_fanout.destructor_executions.append(
                    resolved_action_execution.execution
                )
                binding_hole_fanout.callee_binding_joins.extend(
                    callee_binding_join_by_callee_binding[callee_binding]
                    for callee_binding in (
                        resolved_action_execution.callee_bindings.with_runtime_consumers
                    )
                )
        return binding_hole_fanouts


@typing.final
class ActionPlans:
    """Build action plans while reusing resolved direct-callee interfaces."""

    # TODO: For parallel codegen, guarantee-resolution caching needs keyed
    # synchronization because separate action plans can resolve the same
    # guaranteed position concurrently.

    def __init__(
        self,
        operation_graphs: operation_graph.OperationGraphs,
        entry_action: ast.GlobalTypedName,
    ):
        """Initialize with the validated operation graphs and entry action."""
        self._operation_graphs = operation_graphs
        self._entry_action = entry_action
        self._resolved_actions = operation_graph_action_resolver.ResolvedActions(
            operation_graphs
        )

    def plan_for(self, definition: ast.ActionDefinition) -> ActionPlan:
        """Build the plan for an action.

        Args:
            definition: The validated action definition to plan. Every direct
                callee must already have been planned.
        """
        action = definition.typed_name
        resolved_action = self._resolved_actions.resolve(action)
        builder = _ActionPlanBuilder(resolved_action)
        if action == self._entry_action:
            return builder.build_executed_action()
        return builder.build_triggered_action()
