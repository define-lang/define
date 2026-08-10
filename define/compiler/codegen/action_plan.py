"""DLP 44 lowering for action code generation."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_action_resolver,
    operation_graph_model,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast


@dataclass(slots=True, eq=False)
class ActionFragment:
    """A maximal direct-call chain of Particle Operations."""

    operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath] = field(
        init=False, default_factory=list
    )
    successor_fragments: list[ActionFragment] = field(init=False, default_factory=list)
    triggered_input_successors: list[TriggeredActionInput] = field(
        init=False, default_factory=list
    )
    triggered_action_successors: list[operation_graph_model.ActionTrigger] = field(
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

    resolved_input: operation_graph_action_resolver.CallerInput
    fragments: list[ActionFragment]
    triggered_inputs: list[TriggeredActionInput]
    destructor_triggers: list[operation_graph_model.ActionTrigger]


@dataclass(frozen=True, slots=True)
class _PlanDependencies:
    """Dependencies of one fragment or triggered-action input."""

    local_operations: list[operation_graph_model.PositionOperationNode]
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

    action_trigger: operation_graph_model.ActionTrigger
    callee_input: operation_graph_action_resolver.CallerInput
    guarantee_dependencies: list[operation_graph.GuaranteePath]
    dependency_count: int


@dataclass(frozen=True, slots=True, eq=False)
class GuaranteePublication:
    """Source and target guarantees published by one local Particle Operation."""

    operation: operation_graph_model.PositionOperationNode
    guaranteed_source: tuple[str, ...] | None
    guaranteed_target: tuple[str, ...] | None


@dataclass(frozen=True, slots=True, eq=False)
class GuaranteeDestructorTrigger:
    """A destructor Action Trigger fired by a guarantee."""

    action_trigger: operation_graph_model.ActionTrigger
    guarantee_dependency: operation_graph.GuaranteePath
    triggered_inputs: list[TriggeredActionInput]


@dataclass(frozen=True, slots=True)
class ActionPlan:
    """A split representation of an action at one compilation boundary."""

    fragments: list[ActionFragment]
    execute_fragments: list[ActionFragment]
    caller_inputs: list[CallerInput]
    action_triggers: list[operation_graph_model.ActionTrigger]
    triggered_action_inputs: list[TriggeredActionInput]
    guarantee_destructor_triggers: list[GuaranteeDestructorTrigger]
    guarantee_publications: list[GuaranteePublication]


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
    join, an Action Trigger, guarantee publication, or a dependency supplied
    by the caller.
    """

    def __init__(
        self,
        operations: dict[
            operation_graph_model.PositionOperationNode,
            operation_graph_action_resolver.ResolvedActionOperation,
        ],
        *,
        publishes_guarantees: bool,
        uses_caller_inputs: bool,
    ):
        self._operations = operations
        self._publishes_guarantees = publishes_guarantees
        self._uses_caller_inputs = uses_caller_inputs
        self._local_predecessors: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ] = {}
        self._local_successors: dict[
            operation_graph_model.PositionOperationNode,
            list[operation_graph_model.PositionOperationNode],
        ] = {operation: [] for operation in operations}
        for operation, resolved_operation in operations.items():
            predecessors = resolved_operation.dependencies.local_operations
            self._local_predecessors[operation] = predecessors
            for predecessor in predecessors:
                self._local_successors[predecessor].append(operation)

    def build(self) -> _FragmentTopology:
        fragment_operations = self._fragment_operations()
        fragments = [ActionFragment(operations) for operations in fragment_operations]
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
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
    ) -> list[list[operation_graph_model.PositionOperationNode]]:
        heads = [
            operation
            for operation in self._operations
            if not self._can_follow_predecessor(operation)
        ]
        fragments: list[list[operation_graph_model.PositionOperationNode]] = []
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
        self, operation: operation_graph_model.PositionOperationNode
    ) -> bool:
        predecessors = self._local_predecessors[operation]
        if len(predecessors) != 1:
            return False
        resolved_operation = self._operations[operation]
        if (
            self._uses_caller_inputs and resolved_operation.caller_inputs
        ) or resolved_operation.dependencies.guarantee_dependencies:
            return False
        predecessor = predecessors[0]
        return len(
            self._local_successors[predecessor]
        ) == 1 and not self._must_end_fragment(predecessor)

    def _must_end_fragment(
        self, operation: operation_graph_model.PositionOperationNode
    ) -> bool:
        resolved_operation = self._operations[operation]
        return bool(
            (self._publishes_guarantees and resolved_operation.guaranteed_positions)
            or resolved_operation.triggered_inputs
            or resolved_operation.action_triggers
        )


@dataclass(slots=True)
class _TriggeredActions:
    inputs: list[TriggeredActionInput]
    input_by_resolved_input: dict[
        operation_graph_action_resolver.ResolvedActionTriggerInput,
        TriggeredActionInput,
    ]


@dataclass(slots=True)
class _CallerInputRelationships:
    """Code-generation relationships of one caller input."""

    fragments: list[ActionFragment] = field(default_factory=list)
    triggered_inputs: list[TriggeredActionInput] = field(default_factory=list)
    destructor_triggers: list[operation_graph_model.ActionTrigger] = field(
        default_factory=list
    )


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
        self._operation_graphs = operation_graphs

    def build_executed_action(self) -> ActionPlan:
        """Build a plan started directly through the action's execute method."""
        return self._build(
            [],
            publishes_guarantees=False,
            start_directly=True,
        )

    def build_triggered_action(self) -> ActionPlan:
        """Build the reusable caller-input plan for Action Triggers of this action."""
        return self._build(
            self._resolved_action.caller_inputs,
            publishes_guarantees=True,
            start_directly=False,
        )

    def _build(
        self,
        caller_inputs: list[operation_graph_action_resolver.CallerInput],
        *,
        publishes_guarantees: bool,
        start_directly: bool,
    ) -> ActionPlan:
        topology = _FragmentTopologyBuilder(
            self._resolved_action.operations,
            publishes_guarantees=publishes_guarantees,
            uses_caller_inputs=not start_directly,
        ).build()
        triggered_actions = self._plan_triggered_actions(
            topology.fragment_for_operation,
            caller_inputs,
        )
        guarantee_publications = self._plan_guarantee_publications(
            topology.fragment_for_operation,
            publishes_guarantees=publishes_guarantees,
        )
        self._plan_fragments(topology)
        planned_caller_inputs = self._plan_caller_inputs(
            caller_inputs,
            topology.fragment_for_operation,
            triggered_actions,
        )
        execute_fragments: list[ActionFragment] = []
        if start_directly:
            for fragment in topology.fragments:
                if fragment.dependency_count == 0:
                    execute_fragments.append(fragment)
        return ActionPlan(
            fragments=topology.fragments,
            execute_fragments=execute_fragments,
            caller_inputs=planned_caller_inputs,
            action_triggers=[
                action_trigger.trigger
                for action_trigger in self._resolved_action.action_triggers
            ],
            triggered_action_inputs=triggered_actions.inputs,
            guarantee_destructor_triggers=self._plan_guarantee_destructor_triggers(
                triggered_actions
            ),
            guarantee_publications=guarantee_publications,
        )

    def _plan_triggered_actions(
        self,
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ],
        caller_inputs: list[operation_graph_action_resolver.CallerInput],
    ) -> _TriggeredActions:
        triggered_action_inputs: list[TriggeredActionInput] = []
        input_by_resolved_input: dict[
            operation_graph_action_resolver.ResolvedActionTriggerInput,
            TriggeredActionInput,
        ] = {}
        resolved_action_triggers = self._resolved_action.action_triggers
        for resolved_action_trigger in resolved_action_triggers:
            action_trigger = resolved_action_trigger.trigger
            for resolved_input in resolved_action_trigger.inputs:
                dependencies = resolved_input.caller_dependencies
                planned_dependencies = _PlanDependencies.from_action_dependencies(
                    dependencies,
                    self._operation_graphs,
                )
                dependency_count = (
                    len(dependencies.local_operations)
                    + len(dependencies.guarantee_dependencies)
                    + 1
                )
                # caller_inputs is empty for the entry point action.
                if caller_inputs:
                    dependency_count += len(resolved_input.caller_input_dependencies)
                triggered_input = TriggeredActionInput(
                    action_trigger=action_trigger,
                    callee_input=resolved_input.callee_input,
                    guarantee_dependencies=planned_dependencies.guarantee_dependencies,
                    dependency_count=dependency_count,
                )
                triggered_action_inputs.append(triggered_input)
                input_by_resolved_input[resolved_input] = triggered_input
        for resolved_operation in self._resolved_action.operations.values():
            fragment = fragment_for_operation[resolved_operation.operation]
            for resolved_input in resolved_operation.triggered_inputs:
                fragment.triggered_input_successors.append(
                    input_by_resolved_input[resolved_input]
                )
            for resolved_action_trigger in resolved_operation.action_triggers:
                fragment.triggered_action_successors.append(
                    resolved_action_trigger.trigger
                )
                fragment.execution_input_successors.extend(
                    input_by_resolved_input[resolved_input]
                    for resolved_input in resolved_action_trigger.inputs
                )
        return _TriggeredActions(
            inputs=triggered_action_inputs,
            input_by_resolved_input=input_by_resolved_input,
        )

    def _plan_guarantee_destructor_triggers(
        self,
        triggered_actions: _TriggeredActions,
    ) -> list[GuaranteeDestructorTrigger]:
        guarantee_destructor_triggers: list[GuaranteeDestructorTrigger] = []
        for (
            trigger_guarantee,
            resolved_destructor_triggers,
        ) in self._resolved_action.action_triggers.destructors_by_guarantee():
            guarantee_dependency = self._operation_graphs.resolve_guarantee(
                trigger_guarantee
            )
            for resolved_destructor_trigger in resolved_destructor_triggers:
                guarantee_destructor_triggers.append(
                    GuaranteeDestructorTrigger(
                        action_trigger=resolved_destructor_trigger.trigger,
                        guarantee_dependency=guarantee_dependency,
                        triggered_inputs=[
                            triggered_actions.input_by_resolved_input[resolved_input]
                            for resolved_input in resolved_destructor_trigger.inputs
                        ],
                    )
                )
        return guarantee_destructor_triggers

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
            resolved_operation
        ) in self._resolved_action.guarantee_publication_operations():
            publication_positions = resolved_operation.guaranteed_positions
            operation = resolved_operation.operation
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
            first_dependencies = self._resolved_action.operations[
                fragment.operations[0]
            ].dependencies
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

    def _plan_caller_inputs(
        self,
        resolved_caller_inputs: list[operation_graph_action_resolver.CallerInput],
        fragment_for_operation: dict[
            operation_graph_model.PositionOperationNode, ActionFragment
        ],
        triggered_actions: _TriggeredActions,
    ) -> list[CallerInput]:
        if not resolved_caller_inputs:
            return []
        relationships_by_resolved_input = {
            resolved_input: _CallerInputRelationships()
            for resolved_input in resolved_caller_inputs
        }
        for resolved_operation in self._resolved_action.operations.values():
            fragment = fragment_for_operation[resolved_operation.operation]
            for resolved_input in resolved_operation.caller_inputs:
                relationships = relationships_by_resolved_input[resolved_input]
                relationships.fragments.append(fragment)
                fragment.dependency_count += 1
        for resolved_action_trigger in self._resolved_action.action_triggers:
            for resolved_trigger_input in resolved_action_trigger.inputs:
                triggered_input = triggered_actions.input_by_resolved_input[
                    resolved_trigger_input
                ]
                for resolved_input in resolved_trigger_input.caller_input_dependencies:
                    relationships_by_resolved_input[
                        resolved_input
                    ].triggered_inputs.append(triggered_input)
            caller_input_dependency = resolved_action_trigger.caller_input_dependency
            if caller_input_dependency is not None:
                relationships = relationships_by_resolved_input[caller_input_dependency]
                relationships.destructor_triggers.append(
                    resolved_action_trigger.trigger
                )
                relationships.triggered_inputs.extend(
                    triggered_actions.input_by_resolved_input[resolved_input]
                    for resolved_input in resolved_action_trigger.inputs
                )

        caller_inputs: list[CallerInput] = []
        for resolved_input in resolved_caller_inputs:
            relationships = relationships_by_resolved_input[resolved_input]
            caller_inputs.append(
                CallerInput(
                    resolved_input,
                    relationships.fragments,
                    relationships.triggered_inputs,
                    relationships.destructor_triggers,
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
