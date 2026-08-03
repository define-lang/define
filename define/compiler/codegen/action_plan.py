"""DLP 44 lowering for action code generation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast


@dataclass(slots=True, eq=False)
class ActionFragment:
    """A maximal direct-call chain of Particle Operations."""

    operations: list[operation_graph.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath] = field(
        init=False, default_factory=list
    )
    successor_fragments: list[ActionFragment] = field(init=False, default_factory=list)
    triggered_input_successors: list[TriggeredActionInput] = field(
        init=False, default_factory=list
    )
    triggered_action_successors: list[operation_graph.ActionTrigger] = field(
        init=False, default_factory=list
    )
    execution_input_successors: list[TriggeredActionInput] = field(
        init=False, default_factory=list
    )
    guarantee_publications: list[GuaranteePublication] = field(
        init=False, default_factory=list
    )
    dependency_count: int = field(init=False, default=0)


@dataclass(frozen=True, slots=True, eq=False)
class CallerInput:
    """One dependency input supplied by an action's caller."""

    resolved_input: operation_graph_action_resolver.ResolvedCallerInput
    fragments: list[ActionFragment]
    triggered_inputs: list[TriggeredActionInput]


@dataclass(frozen=True, slots=True)
class _PlanDependencies:
    """Dependencies of one fragment or triggered-action input."""

    local_operations: list[operation_graph.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath]

    @staticmethod
    def from_action_dependencies(
        dependencies: operation_graph_action_resolver.ActionDependencies,
        operation_graphs: operation_graph.OperationGraphs,
    ) -> _PlanDependencies:
        return _PlanDependencies(
            local_operations=dependencies.local_operations,
            guarantee_dependencies=[
                operation_graphs.resolve_guarantee(dependency)
                for dependency in dependencies.guarantee_dependencies
            ],
        )


@dataclass(slots=True, eq=False)
class TriggeredActionInput:
    """One direct callee input connected to dependencies in its caller."""

    action_trigger: operation_graph.ActionTrigger
    callee_input: operation_graph_action_resolver.ResolvedCallerInput
    guarantee_dependencies: list[operation_graph.GuaranteePath]
    dependency_count: int


@dataclass(frozen=True, slots=True, eq=False)
class GuaranteePublication:
    """Source and target guarantees published by one local Particle Operation."""

    operation: operation_graph.PositionOperationNode
    guaranteed_source: tuple[str, ...] | None
    guaranteed_target: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """A split representation of an action at one compilation boundary."""

    fragments: list[ActionFragment]
    execute_fragments: list[ActionFragment]
    caller_inputs: list[CallerInput]
    action_triggers: list[operation_graph.ActionTrigger]
    triggered_action_inputs: list[TriggeredActionInput]
    guarantee_publications: list[GuaranteePublication]


@dataclass(slots=True)
class _FragmentTopology:
    """The fragment structure of one action before its Action Plan is assembled.

    Each fragment is a maximal serial chain of Particle Operations. The topology
    records the Particle Operations in each fragment and the connections between
    fragments.
    """

    fragments: list[ActionFragment]
    fragment_for_operation: dict[operation_graph.PositionOperationNode, ActionFragment]


@typing.final
class _FragmentTopologyBuilder:
    """Partition one action's Particle Operations into code-generation fragments.

    A fragment ends where a direct method call would not preserve fan-out, a
    join, an Action Triggering, guarantee publication, or a dependency supplied
    by the caller.
    """

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        dependencies: dict[
            operation_graph.PositionOperationNode,
            operation_graph_action_resolver.ActionDependencies,
        ],
        guaranteed_positions_by_operation: dict[
            operation_graph.PositionOperationNode, tuple[tuple[str, ...], ...]
        ],
        resolved_action_triggers: list[
            operation_graph_action_resolver.ResolvedActionTrigger
        ],
        caller_inputs: list[operation_graph_action_resolver.ResolvedCallerInput],
    ):
        self._dependencies = dependencies
        self._operations = [
            node
            for node in graph.nodes
            if isinstance(node, operation_graph.PositionOperationNode)
        ]
        self._local_predecessors: dict[
            operation_graph.PositionOperationNode,
            list[operation_graph.PositionOperationNode],
        ] = {}
        self._local_successors: dict[
            operation_graph.PositionOperationNode,
            list[operation_graph.PositionOperationNode],
        ] = {operation: [] for operation in self._operations}
        for operation, operation_dependencies in dependencies.items():
            predecessors = operation_dependencies.local_operations
            self._local_predecessors[operation] = predecessors
            for predecessor in predecessors:
                self._local_successors[predecessor].append(operation)

        self._must_end_fragment_operations = set(guaranteed_positions_by_operation)
        for resolved_action_trigger in resolved_action_triggers:
            for triggered_input in resolved_action_trigger.inputs:
                self._must_end_fragment_operations.update(
                    triggered_input.caller_dependencies.local_operations
                )
            self._must_end_fragment_operations.add(
                resolved_action_trigger.trigger.trigger_operation
            )
        self._caller_input_consumer_operations = {
            operation
            for caller_input in caller_inputs
            for operation in caller_input.operation_consumers
        }

    def build(self) -> _FragmentTopology:
        fragment_operations = self._fragment_operations()
        fragments = [ActionFragment(operations) for operations in fragment_operations]
        fragment_for_operation: dict[
            operation_graph.PositionOperationNode, ActionFragment
        ] = {}
        for fragment in fragments:
            for operation in fragment.operations:
                fragment_for_operation[operation] = fragment
        for fragment in fragments:
            fragment.successor_fragments = [
                fragment_for_operation[successor]
                for successor in self._local_successors[fragment.operations[-1]]
            ]
        return _FragmentTopology(
            fragments,
            fragment_for_operation,
        )

    def _fragment_operations(
        self,
    ) -> list[list[operation_graph.PositionOperationNode]]:
        heads = [
            operation
            for operation in self._operations
            if not self._can_follow_predecessor(operation)
        ]
        fragments: list[list[operation_graph.PositionOperationNode]] = []
        for head in heads:
            chain = [head]
            while True:
                successors = self._local_successors[chain[-1]]
                if len(successors) != 1:
                    break
                successor = successors[0]
                if not self._can_follow_predecessor(successor):
                    break
                chain.append(successor)
            fragments.append(chain)
        return fragments

    def _can_follow_predecessor(
        self, operation: operation_graph.PositionOperationNode
    ) -> bool:
        predecessors = self._local_predecessors[operation]
        if len(predecessors) != 1:
            return False
        operation_dependencies = self._dependencies[operation]
        if (
            operation in self._caller_input_consumer_operations
            or operation_dependencies.guarantee_dependencies
        ):
            return False
        predecessor = predecessors[0]
        return (
            len(self._local_successors[predecessor]) == 1
            and predecessor not in self._must_end_fragment_operations
        )


@dataclass(slots=True)
class _TriggeredActions:
    inputs: list[TriggeredActionInput]
    input_by_resolved_input: dict[
        operation_graph_action_resolver.ResolvedActionTriggerInput,
        TriggeredActionInput,
    ]


@typing.final
class _ActionPlanBuilder:
    """Build code-generation plans from one action operation graph."""

    def __init__(
        self,
        resolved_action: operation_graph_action_resolver.ResolvedAction,
        operation_graphs: operation_graph.OperationGraphs,
    ):
        """Initialize for one action and its validated operation graph."""
        self._resolved_action = resolved_action
        self._graph = resolved_action.graph
        self._operation_graphs = operation_graphs

    def build_executed_action(self) -> ActionPlan:
        """Build a plan started directly through the action's execute method."""
        return self._build(
            self._resolved_action.dependencies_by_operation,
            {},
            [],
            start_directly=True,
        )

    def build_triggered_action(self) -> ActionPlan:
        """Build the reusable caller-input plan for triggerings of this action."""
        return self._build(
            self._resolved_action.dependencies_by_operation,
            self._graph.guaranteed_positions_by_operation,
            self._resolved_action.caller_inputs,
            start_directly=False,
        )

    def _build(
        self,
        dependencies: dict[
            operation_graph.PositionOperationNode,
            operation_graph_action_resolver.ActionDependencies,
        ],
        guaranteed_positions_by_operation: dict[
            operation_graph.PositionOperationNode, tuple[tuple[str, ...], ...]
        ],
        caller_inputs: list[operation_graph_action_resolver.ResolvedCallerInput],
        *,
        start_directly: bool,
    ) -> ActionPlan:
        topology = _FragmentTopologyBuilder(
            self._graph,
            dependencies,
            guaranteed_positions_by_operation,
            self._resolved_action.action_triggers,
            caller_inputs,
        ).build()
        triggered_actions = self._plan_triggered_actions(
            topology.fragment_for_operation,
            caller_inputs,
        )
        guarantee_publications = self._plan_guarantee_publications(
            guaranteed_positions_by_operation,
            topology.fragment_for_operation,
        )
        self._plan_fragments(
            dependencies,
            topology,
            caller_inputs,
        )
        execute_fragments: list[ActionFragment] = []
        if start_directly:
            for fragment in topology.fragments:
                if fragment.dependency_count == 0:
                    execute_fragments.append(fragment)
        return ActionPlan(
            fragments=topology.fragments,
            execute_fragments=execute_fragments,
            caller_inputs=self._plan_caller_inputs(
                caller_inputs,
                topology.fragment_for_operation,
                triggered_actions,
            ),
            action_triggers=[
                action_trigger.trigger
                for action_trigger in self._resolved_action.action_triggers
            ],
            triggered_action_inputs=triggered_actions.inputs,
            guarantee_publications=guarantee_publications,
        )

    def _plan_triggered_actions(
        self,
        fragment_for_operation: dict[
            operation_graph.PositionOperationNode, ActionFragment
        ],
        caller_inputs: list[operation_graph_action_resolver.ResolvedCallerInput],
    ) -> _TriggeredActions:
        triggered_action_inputs: list[TriggeredActionInput] = []
        input_by_resolved_input: dict[
            operation_graph_action_resolver.ResolvedActionTriggerInput,
            TriggeredActionInput,
        ] = {}
        for resolved_action_trigger in self._resolved_action.action_triggers:
            action_trigger = resolved_action_trigger.trigger
            inputs_for_action_trigger: list[TriggeredActionInput] = []
            for resolved_input in resolved_action_trigger.inputs:
                dependencies = resolved_input.caller_dependencies
                planned_dependencies = _PlanDependencies.from_action_dependencies(
                    dependencies,
                    self._operation_graphs,
                )
                triggered_input = TriggeredActionInput(
                    action_trigger=action_trigger,
                    callee_input=resolved_input.callee_input,
                    guarantee_dependencies=planned_dependencies.guarantee_dependencies,
                    dependency_count=(
                        len(dependencies.local_operations)
                        + len(dependencies.guarantee_dependencies)
                        + 1
                    ),
                )
                triggered_action_inputs.append(triggered_input)
                inputs_for_action_trigger.append(triggered_input)
                input_by_resolved_input[resolved_input] = triggered_input
                for operation in planned_dependencies.local_operations:
                    fragment_for_operation[operation].triggered_input_successors.append(
                        triggered_input
                    )
            fragment = fragment_for_operation[action_trigger.trigger_operation]
            fragment.triggered_action_successors.append(action_trigger)
            fragment.execution_input_successors.extend(inputs_for_action_trigger)
        for caller_input in caller_inputs:
            for consumer in caller_input.triggered_input_consumers:
                input_by_resolved_input[consumer].dependency_count += 1
        return _TriggeredActions(
            inputs=triggered_action_inputs,
            input_by_resolved_input=input_by_resolved_input,
        )

    def _plan_guarantee_publications(
        self,
        guaranteed_positions_by_operation: dict[
            operation_graph.PositionOperationNode, tuple[tuple[str, ...], ...]
        ],
        fragment_for_operation: dict[
            operation_graph.PositionOperationNode, ActionFragment
        ],
    ) -> list[GuaranteePublication]:
        publications: list[GuaranteePublication] = []
        for (
            operation,
            publication_positions,
        ) in guaranteed_positions_by_operation.items():
            guaranteed_source = None
            if isinstance(operation, operation_graph.MoveNode):
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

    def _plan_fragments(
        self,
        dependencies: dict[
            operation_graph.PositionOperationNode,
            operation_graph_action_resolver.ActionDependencies,
        ],
        topology: _FragmentTopology,
        caller_inputs: list[operation_graph_action_resolver.ResolvedCallerInput],
    ):
        for fragment in topology.fragments:
            first_dependencies = dependencies[fragment.operations[0]]
            planned_dependencies = _PlanDependencies.from_action_dependencies(
                first_dependencies,
                self._operation_graphs,
            )
            fragment.guarantee_dependencies = (
                planned_dependencies.guarantee_dependencies
            )
            fragment.dependency_count = len(first_dependencies.local_operations) + len(
                planned_dependencies.guarantee_dependencies
            )
        for caller_input in caller_inputs:
            for operation in caller_input.operation_consumers:
                topology.fragment_for_operation[operation].dependency_count += 1

    def _plan_caller_inputs(
        self,
        resolved_caller_inputs: list[
            operation_graph_action_resolver.ResolvedCallerInput
        ],
        fragment_for_operation: dict[
            operation_graph.PositionOperationNode, ActionFragment
        ],
        triggered_actions: _TriggeredActions,
    ) -> list[CallerInput]:
        caller_inputs: list[CallerInput] = []
        for resolved_caller_input in resolved_caller_inputs:
            fragments = [
                fragment_for_operation[operation]
                for operation in resolved_caller_input.operation_consumers
            ]
            triggered_inputs = [
                triggered_actions.input_by_resolved_input[triggered_input]
                for triggered_input in resolved_caller_input.triggered_input_consumers
            ]
            caller_inputs.append(
                CallerInput(
                    resolved_caller_input,
                    fragments,
                    triggered_inputs,
                )
            )
        return caller_inputs


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
        builder = _ActionPlanBuilder(resolved_action, self._operation_graphs)
        if action == self._entry_action:
            return builder.build_executed_action()
        return builder.build_triggered_action()
