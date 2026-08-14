"""Resolves symbolic dependencies between per-action operation graphs."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
)

# Resolution must be limited to substitutions that codegen can perform while
# consuming an operation graph. Operation graphs must already contain the
# correct minimal direct dependencies; resolution must never compensate for
# missing graph-construction information by analyzing or repairing the resolved
# graph.

if typing.TYPE_CHECKING:
    from collections.abc import (
        Iterable,
        Mapping,
    )

    from define.compiler import ast


type _CallerInputNode = (
    operation_graph_model.ActionParentLastOperationNode
    | operation_graph_model.RequirementNode
)
type _CallerInputDependencyNode = (
    _CallerInputNode | operation_graph_model.CallerEmptyRuleDependenciesNode
)
type CallerInput = (
    _CallerInputDependencyNode | operation_graph_model.CallerEmptyRuleDependencies
)


@dataclass(frozen=True, slots=True)
class ActionDependencies:
    """Dependencies resolved within one reusable action graph."""

    local_operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: list[operation_graph.GuaranteePath]


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionOperation:
    """One operation and its relationships within one reusable action."""

    operation: operation_graph_model.PositionOperationNode
    dependencies: ActionDependencies
    caller_inputs: list[CallerInput]
    triggered_inputs: list[ResolvedActionTriggerInput]
    action_triggers: list[ResolvedActionTrigger]


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedDestructionOperation(ResolvedActionOperation):
    """One Destruction Fact Destroy and its caller-contribution relationships."""

    operation: operation_graph_model.DestructionFactDestroyNode
    destruction_dependencies: list[operation_graph_model.DestructionDependency]


def _append_action_dependency(
    node: operation_graph_model.OperationNode,
    dependencies: ActionDependencies,
    caller_inputs: list[CallerInput],
    operation_graphs: operation_graph.OperationGraphs,
):
    """Add one ordinary dependency to its resolved action relationship."""
    match node:
        case operation_graph_model.PositionOperationNode():
            dependencies.local_operations.append(node)
        case (
            operation_graph_model.ActionParentLastOperationNode()
            | operation_graph_model.RequirementNode()
            | operation_graph_model.CallerEmptyRuleDependenciesNode()
        ):
            caller_inputs.append(node)
        case operation_graph_model.GuaranteeNode():
            dependencies.guarantee_dependencies.append(
                operation_graphs.resolve_guarantee(node)
            )
        case _:
            raise TypeError(f"unknown operation node type: {type(node).__name__}")


def _partition_caller_dependencies(
    nodes: Iterable[operation_graph_model.OperationNode],
    operation_graphs: operation_graph.OperationGraphs,
) -> tuple[ActionDependencies, list[CallerInput]]:
    """Separate local Particle Operations and guarantees from caller inputs."""
    dependencies = ActionDependencies([], [])
    caller_inputs: list[CallerInput] = []
    for node in nodes:
        _append_action_dependency(node, dependencies, caller_inputs, operation_graphs)
    return dependencies, caller_inputs


@dataclass(slots=True, eq=False)
class ResolvedActionTriggerInput:
    """One direct callee input resolved from the caller's perspective."""

    callee_input: CallerInput
    caller_dependencies: ActionDependencies
    caller_input_dependencies: list[CallerInput]
    contributed_destruction_operations: list[
        operation_graph_model.DestructionFragmentDestroyNode
    ] = field(default_factory=list)


def resolve_action_trigger_input(
    trigger: operation_graph_model.ActionTrigger,
    operation_graphs: operation_graph.OperationGraphs,
    callee_input: CallerInput,
) -> ResolvedActionTriggerInput:
    """Resolve one callee input from the direct caller's perspective."""
    if isinstance(callee_input, operation_graph_model.CallerEmptyRuleDependencies):
        caller_empty_rule_dependencies = callee_input
    elif isinstance(
        callee_input, operation_graph_model.CallerEmptyRuleDependenciesNode
    ):
        caller_empty_rule_dependencies = callee_input.caller_empty_rule_dependencies
    else:
        dependencies, caller_inputs = _partition_caller_dependencies(
            (trigger.caller_dependency_for_input(callee_input),),
            operation_graphs,
        )
        return ResolvedActionTriggerInput(callee_input, dependencies, caller_inputs)

    substitution = trigger.substitute_caller_empty_rule_dependencies(
        caller_empty_rule_dependencies
    )
    dependencies, caller_inputs = _partition_caller_dependencies(
        substitution.dependency_nodes,
        operation_graphs,
    )
    if substitution.caller_empty_rule_dependencies is not None:
        caller_inputs.append(substitution.caller_empty_rule_dependencies)
    return ResolvedActionTriggerInput(callee_input, dependencies, caller_inputs)


@typing.final
class ResolvedActionTriggerInputs:
    """The inputs of one Action Trigger resolved from the caller's perspective."""

    def __init__(
        self,
        direct_inputs: dict[CallerInput, ResolvedActionTriggerInput],
    ):
        """Initialize with the Action Trigger's direct callee inputs."""
        self._direct_inputs = direct_inputs

    @classmethod
    def resolve(
        cls,
        trigger: operation_graph_model.ActionTrigger,
        operation_graphs: operation_graph.OperationGraphs,
        callee_inputs: Iterable[CallerInput],
        destruction_fragments: Iterable[
            operation_graph_model.ContributedDestructionFragment
        ],
    ) -> typing.Self:
        """Resolve the inputs and their caller-contributed destruction fragments."""
        direct_inputs: dict[CallerInput, ResolvedActionTriggerInput] = {}
        for callee_input in callee_inputs:
            direct_inputs[callee_input] = resolve_action_trigger_input(
                trigger,
                operation_graphs,
                callee_input,
            )
        inputs = cls(direct_inputs)
        inputs._set_contributed_destruction_operations_on_callee_nodes(
            destruction_fragments,
            operation_graphs,
        )
        return inputs

    def values(self) -> Iterable[ResolvedActionTriggerInput]:
        """Return the direct callee inputs in their established order."""
        return self._direct_inputs.values()

    def __getitem__(self, callee_input: CallerInput) -> ResolvedActionTriggerInput:
        """Return one direct resolved callee input."""
        return self._direct_inputs[callee_input]

    def get(self, callee_input: CallerInput) -> ResolvedActionTriggerInput | None:
        """Return one direct resolved callee input, if present."""
        return self._direct_inputs.get(callee_input)

    def _set_contributed_destruction_operations_on_callee_nodes(
        self,
        fragments: Iterable[operation_graph_model.ContributedDestructionFragment],
        operation_graphs: operation_graph.OperationGraphs,
    ):
        # Each contributed destruction fragment belongs to one direct callee node.
        # The fragment and callee node depend on the same Particle Operation,
        # Action Guarantee, or propagated operation-graph node. Index the direct
        # callee nodes by those resolved dependencies, then associate each fragment
        # with the earliest matching callee node. Choosing the earliest preserves
        # callee-node order when one dependency satisfies more than one callee node.
        input_indexes: dict[ResolvedActionTriggerInput, int] = {}
        inputs_by_local_operation: dict[
            operation_graph_model.PositionOperationNode,
            ResolvedActionTriggerInput,
        ] = {}
        inputs_by_guarantee: dict[
            tuple[
                tuple[operation_graph_model.ActionTrigger, ...],
                operation_graph_model.PositionOperationNode,
            ],
            ResolvedActionTriggerInput,
        ] = {}
        inputs_by_caller_input: dict[
            CallerInput,
            ResolvedActionTriggerInput,
        ] = {}
        for input_index, resolved_input in enumerate(self._direct_inputs.values()):
            input_indexes[resolved_input] = input_index
            # A RequirementNode, ActionParentLastOperationNode, or
            # CallerEmptyRuleDependenciesNode can resolve directly to a caller
            # Particle Operation. A contributed Destroy that follows the same
            # Particle Operation belongs with that callee node.
            for operation in resolved_input.caller_dependencies.local_operations:
                _ = inputs_by_local_operation.setdefault(
                    operation,
                    resolved_input,
                )
            # A callee node can instead resolve through an Action Guarantee. The
            # sequence of Action Triggers and the guaranteed Particle Operation
            # identify the Guarantee that supplied the required particle.
            for guarantee in resolved_input.caller_dependencies.guarantee_dependencies:
                _ = inputs_by_guarantee.setdefault(
                    (tuple(guarantee.triggers), guarantee.operation),
                    resolved_input,
                )
            # When the direct caller cannot satisfy the callee node, its
            # RequirementNode, ActionParentLastOperationNode, or
            # CallerEmptyRuleDependenciesNode is passed to the next caller.
            for caller_input in resolved_input.caller_input_dependencies:
                _ = inputs_by_caller_input.setdefault(
                    caller_input,
                    resolved_input,
                )
        for fragment in fragments:
            dependencies, caller_inputs = _partition_caller_dependencies(
                fragment.contribution_dependencies,
                operation_graphs,
            )
            candidate_inputs: list[ResolvedActionTriggerInput] = []
            # A contributed Destroy that follows a caller Particle Operation
            # belongs with the callee node resolved to that Particle Operation.
            for operation in dependencies.local_operations:
                resolved_input = inputs_by_local_operation.get(operation)
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            # A contributed Destroy that follows an Action Guarantee belongs with
            # the callee node resolved through the same sequence of Action
            # Triggers and the same guaranteed Particle Operation.
            for guarantee in dependencies.guarantee_dependencies:
                resolved_input = inputs_by_guarantee.get(
                    (tuple(guarantee.triggers), guarantee.operation)
                )
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            # A contributed Destroy whose dependency is passed to the next caller
            # belongs with the callee node that passes the same operation-graph
            # node to that caller.
            for caller_input in caller_inputs:
                resolved_input = inputs_by_caller_input.get(caller_input)
                if resolved_input is not None:
                    candidate_inputs.append(resolved_input)
            callee_node = min(candidate_inputs, key=input_indexes.__getitem__)
            callee_node.contributed_destruction_operations.extend(fragment.operations)


@dataclass(slots=True, eq=False)
class ResolvedActionTrigger:
    """The dependency interface of one direct Action Trigger."""

    trigger: operation_graph_model.ActionTrigger
    guarantee_dependency: operation_graph.GuaranteePath | None
    forwards_destruction_connections: bool
    inputs: ResolvedActionTriggerInputs

    @classmethod
    def resolve(
        cls,
        caller_graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        trigger: operation_graph_model.ActionTrigger,
        callee: ResolvedAction,
        destruction_fragments: Iterable[
            operation_graph_model.ContributedDestructionFragment
        ],
    ) -> typing.Self:
        """Resolve one direct Action Trigger from the caller's perspective."""
        trigger_operation = trigger.trigger_operation
        guarantee_dependency = None
        if isinstance(trigger_operation, operation_graph_model.GuaranteeNode):
            guarantee_dependency = operation_graphs.resolve_guarantee(trigger_operation)
        inputs = ResolvedActionTriggerInputs.resolve(
            trigger,
            operation_graphs,
            callee.caller_inputs,
            destruction_fragments,
        )
        return cls(
            trigger,
            guarantee_dependency,
            caller_graph.propagates_destruction_from_trigger_to_caller(trigger),
            inputs,
        )


@dataclass(frozen=True, slots=True)
class _ActionTriggerResolution:
    """Action Triggers and their relationships within one reusable action."""

    action_triggers: list[ResolvedActionTrigger]
    triggered_inputs_by_operation: dict[
        operation_graph_model.PositionOperationNode,
        list[ResolvedActionTriggerInput],
    ]
    action_triggers_by_operation: dict[
        operation_graph_model.PositionOperationNode,
        list[ResolvedActionTrigger],
    ]


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action."""

    graph: operation_graph.OperationGraph
    operations: dict[
        operation_graph_model.PositionOperationNode, ResolvedActionOperation
    ]
    caller_inputs: tuple[CallerInput, ...]
    action_triggers: list[ResolvedActionTrigger]
    destruction_contributions: dict[
        operation_graph_model.DestructionDependency,
        operation_graph_model.DestructionContribution,
    ]


@typing.final
class _ActionResolver:
    """Build the dependency interface of one reusable action."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        operation_graphs: operation_graph.OperationGraphs,
        resolved_callees: Mapping[ast.GlobalTypedName, ResolvedAction],
    ):
        """Initialize resolution with one graph and its resolved direct callees."""
        self._graph = graph
        self._operation_graphs = operation_graphs
        self._resolved_callees = resolved_callees

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Triggers."""
        action_trigger_resolution = self._resolve_action_triggers()
        operations = self._resolve_operations(action_trigger_resolution)
        return ResolvedAction(
            graph=self._graph,
            operations=operations,
            caller_inputs=self._build_caller_inputs(
                operations,
                action_trigger_resolution,
            ),
            action_triggers=action_trigger_resolution.action_triggers,
            destruction_contributions=self._operation_graphs.destruction_contributions(
                self._graph
            ),
        )

    @staticmethod
    def _build_caller_inputs(
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ],
        action_trigger_resolution: _ActionTriggerResolution,
    ) -> tuple[CallerInput, ...]:
        caller_inputs: dict[CallerInput, None] = {}
        for resolved_operation in operations.values():
            for caller_input in resolved_operation.caller_inputs:
                caller_inputs[caller_input] = None
        for resolved_trigger in action_trigger_resolution.action_triggers:
            for resolved_input in resolved_trigger.inputs.values():
                for caller_input in resolved_input.caller_input_dependencies:
                    caller_inputs[caller_input] = None
            # The destructor might not act on an implied position, so resolving its
            # inputs does not necessarily discover this dependency.
            caller_input_dependency = resolved_trigger.trigger.caller_input_dependency
            if caller_input_dependency is not None:
                caller_inputs[caller_input_dependency] = None
        return tuple(caller_inputs)

    def _resolve_operations(
        self,
        action_trigger_resolution: _ActionTriggerResolution,
    ) -> dict[operation_graph_model.PositionOperationNode, ResolvedActionOperation]:
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ] = {}
        for operation in self._graph.nodes:
            if not isinstance(operation, operation_graph_model.PositionOperationNode):
                continue
            (
                dependencies,
                caller_inputs,
                destruction_dependencies,
            ) = self._resolve_dependencies(
                operation.depends_on,
            )
            triggered_inputs = (
                action_trigger_resolution.triggered_inputs_by_operation.get(operation)
            )
            if triggered_inputs is None:
                triggered_inputs = []
            action_triggers = (
                action_trigger_resolution.action_triggers_by_operation.get(operation)
            )
            if action_triggers is None:
                action_triggers = []
            if isinstance(operation, operation_graph_model.DestructionFactDestroyNode):
                operations[operation] = ResolvedDestructionOperation(
                    operation=operation,
                    dependencies=dependencies,
                    caller_inputs=caller_inputs,
                    triggered_inputs=triggered_inputs,
                    action_triggers=action_triggers,
                    destruction_dependencies=destruction_dependencies,
                )
            else:
                operations[operation] = ResolvedActionOperation(
                    operation,
                    dependencies,
                    caller_inputs,
                    triggered_inputs,
                    action_triggers,
                )
        return operations

    def _resolve_action_triggers(self) -> _ActionTriggerResolution:
        action_triggers: list[ResolvedActionTrigger] = []
        triggered_inputs_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[ResolvedActionTriggerInput],
        ] = {}
        action_triggers_by_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[ResolvedActionTrigger],
        ] = {}
        for trigger in self._graph.triggers:
            callee = self._resolved_callees[trigger.callee_action_name]
            destruction_fragments = self._graph.contributed_destruction_fragments_for(
                trigger
            )
            resolved_trigger = ResolvedActionTrigger.resolve(
                self._graph,
                self._operation_graphs,
                trigger,
                callee,
                destruction_fragments,
            )
            action_triggers.append(resolved_trigger)
            for resolved_input in resolved_trigger.inputs.values():
                for operation in resolved_input.caller_dependencies.local_operations:
                    triggered_inputs_by_operation.setdefault(operation, []).append(
                        resolved_input
                    )
            trigger_operation = trigger.trigger_operation
            if isinstance(
                trigger_operation,
                operation_graph_model.PositionOperationNode,
            ):
                action_triggers_by_operation.setdefault(trigger_operation, []).append(
                    resolved_trigger
                )
        return _ActionTriggerResolution(
            action_triggers,
            triggered_inputs_by_operation,
            action_triggers_by_operation,
        )

    def _resolve_dependencies(
        self,
        dependency_nodes: Iterable[operation_graph_model.OperationNode],
    ) -> tuple[
        ActionDependencies,
        list[CallerInput],
        list[operation_graph_model.DestructionDependency],
    ]:
        dependencies = ActionDependencies([], [])
        caller_inputs: list[CallerInput] = []
        destruction_dependencies: list[operation_graph_model.DestructionDependency] = []
        for dependency in dependency_nodes:
            if isinstance(
                dependency, operation_graph_model.DestructionContributionNode
            ):
                destruction_dependencies.append(
                    self._operation_graphs.resolve_destruction_dependency(dependency)
                )
                continue
            _append_action_dependency(
                dependency,
                dependencies,
                caller_inputs,
                self._operation_graphs,
            )
        return (
            dependencies,
            caller_inputs,
            destruction_dependencies,
        )


@typing.final
class ResolvedActions:
    """Resolve and retain reusable action dependency interfaces."""

    # TODO: For parallel codegen, coordinate each action with a single-assignment
    # future. The first thread to claim an action resolves it; other threads wait
    # for the same result or exception.

    def __init__(self, operation_graphs: operation_graph.OperationGraphs):
        """Initialize with the validated operation graphs."""
        self._operation_graphs = operation_graphs
        self._resolved: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, ResolvedAction
        ] = typed_name_dict.TypedNameDict()

    def resolve(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Resolve an action whose direct callees have already been resolved."""
        resolved = self._resolved.get(action)
        if resolved is not None:
            return resolved
        resolved = _ActionResolver(
            self._operation_graphs[action],
            self._operation_graphs,
            self._resolved,
        ).resolve()
        self._resolved[action] = resolved
        return resolved

    def __getitem__(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Return a resolved action."""
        return self._resolved[action]
