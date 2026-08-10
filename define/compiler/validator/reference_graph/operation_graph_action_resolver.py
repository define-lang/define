"""Resolves symbolic dependencies between per-action operation graphs."""

from __future__ import annotations

import typing
from dataclasses import dataclass

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
        ItemsView,
        Iterable,
        Iterator,
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
    guarantee_dependencies: list[operation_graph_model.GuaranteeNode]


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionOperation:
    """One operation and its relationships within one reusable action."""

    operation: operation_graph_model.PositionOperationNode
    dependencies: ActionDependencies
    guaranteed_positions: tuple[tuple[str, ...], ...]
    caller_inputs: list[CallerInput]
    triggered_inputs: list[ResolvedActionTriggerInput]
    action_triggers: list[ResolvedActionTrigger]


def _partition_dependencies(
    nodes: Iterable[operation_graph_model.OperationNode],
) -> tuple[ActionDependencies, list[CallerInput]]:
    """Separate local Particle Operations and guarantees from caller inputs."""
    local_operations: list[operation_graph_model.PositionOperationNode] = []
    guarantee_dependencies: list[operation_graph_model.GuaranteeNode] = []
    caller_input_dependencies: list[CallerInput] = []
    for node in nodes:
        match node:
            case operation_graph_model.PositionOperationNode():
                local_operations.append(node)
            case (
                operation_graph_model.ActionParentLastOperationNode()
                | operation_graph_model.RequirementNode()
                | operation_graph_model.CallerEmptyRuleDependenciesNode()
            ):
                caller_input_dependencies.append(node)
            case operation_graph_model.GuaranteeNode():
                guarantee_dependencies.append(node)
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")
    return (
        ActionDependencies(local_operations, guarantee_dependencies),
        caller_input_dependencies,
    )


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionTriggerInput:
    """One direct callee input resolved from the caller's perspective."""

    callee_input: CallerInput
    caller_dependencies: ActionDependencies
    caller_input_dependencies: list[CallerInput]


@typing.final
class _ActionTriggerDependencyResolver:
    """Resolve a triggered action's caller inputs in its caller's operation graph."""

    def __init__(
        self,
        caller_graph: operation_graph.OperationGraph,
        trigger: operation_graph_model.ActionTrigger,
    ):
        """Initialize with one direct caller and Action Trigger."""
        self._caller_graph = caller_graph
        self._trigger = trigger

    def resolve_input(
        self, callee_input: CallerInput
    ) -> tuple[ActionDependencies, list[CallerInput]]:
        """Return action-local dependencies and caller inputs for one callee input."""
        if isinstance(callee_input, operation_graph_model.CallerEmptyRuleDependencies):
            return self._resolve_caller_empty_rule_input(callee_input)
        if isinstance(
            callee_input, operation_graph_model.CallerEmptyRuleDependenciesNode
        ):
            return self._resolve_caller_empty_rule_input(
                callee_input.caller_empty_rule_dependencies
            )
        return _partition_dependencies(
            (self._caller_dependency_for_input_node(callee_input),)
        )

    def _resolve_caller_empty_rule_input(
        self,
        callee_input: operation_graph_model.CallerEmptyRuleDependencies,
    ) -> tuple[ActionDependencies, list[CallerInput]]:
        """Resolve propagated Empty Rule dependencies into the direct caller."""
        substitution = self._caller_graph.substitute_caller_empty_rule_dependencies(
            callee_input, self._trigger.bindings
        )
        dependencies, caller_input_dependencies = _partition_dependencies(
            substitution.dependency_nodes
        )
        if substitution.caller_empty_rule_dependencies is not None:
            caller_input_dependencies.append(
                substitution.caller_empty_rule_dependencies
            )
        return dependencies, caller_input_dependencies

    def _caller_dependency_for_input_node(
        self,
        node: _CallerInputNode,
    ) -> operation_graph_model.ActionParentOperationNode:
        if isinstance(node, operation_graph_model.ActionParentLastOperationNode):
            return self._trigger.action_parent_last_operation
        # Direct bindings are already constant-time and are the common path.
        # Checking them before the cache avoids its lookup, allocation, and
        # insertion overhead when there is no requirement chain to traverse.
        binding = self._trigger.bindings.get(node.requirement_position)
        if binding is not None:
            return binding.operation

        # Position Requirements form a chain through parent names, so this node has
        # exactly one direct input: the nearest parent-name requirement, or the
        # action parent's last operation when there is no parent-name requirement.
        (parent_input,) = node.depends_on
        if isinstance(
            parent_input, operation_graph_model.ActionParentLastOperationNode
        ):
            return self._trigger.action_parent_last_operation
        return self._trigger.bindings[parent_input.requirement_position].operation


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionTrigger:
    """The dependency interface of one direct Action Trigger."""

    trigger: operation_graph_model.ActionTrigger
    inputs: list[ResolvedActionTriggerInput]
    caller_input_dependency: CallerInput | None

    def input_for(self, callee_input: CallerInput) -> ResolvedActionTriggerInput:
        """Return the resolution of ``callee_input`` through this Action Trigger."""
        # This is inefficient but acceptable because this is used only by the
        # test-only resolved-operation-graph renderer.
        return next(
            resolved_input
            for resolved_input in self.inputs
            if resolved_input.callee_input is callee_input
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
    destructor_triggers_by_guarantee: dict[
        operation_graph_model.GuaranteeNode,
        list[ResolvedActionTrigger],
    ]


@typing.final
class ResolvedActionTriggers:
    """Resolved Action Triggers and their guarantee reverse index."""

    def __init__(
        self,
        triggers: list[ResolvedActionTrigger],
        destructors_by_guarantee: dict[
            operation_graph_model.GuaranteeNode,
            list[ResolvedActionTrigger],
        ],
    ):
        """Initialize with all resolved Action Triggers."""
        self._triggers = triggers
        self._destructors_by_guarantee = destructors_by_guarantee

    def __iter__(self) -> Iterator[ResolvedActionTrigger]:
        """Iterate over every resolved Action Trigger."""
        return iter(self._triggers)

    def __len__(self) -> int:
        """Return the number of resolved Action Triggers."""
        return len(self._triggers)

    def destructors_by_guarantee(
        self,
    ) -> ItemsView[operation_graph_model.GuaranteeNode, list[ResolvedActionTrigger]]:
        """Return guarantees and the destructors they trigger."""
        return self._destructors_by_guarantee.items()


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action."""

    graph: operation_graph.OperationGraph
    operations: dict[
        operation_graph_model.PositionOperationNode, ResolvedActionOperation
    ]
    caller_inputs: list[CallerInput]
    action_triggers: ResolvedActionTriggers

    def guarantee_publication_operations(self) -> Iterator[ResolvedActionOperation]:
        """Iterate over guarantee-publishing operations in publication order."""
        for operation in self.graph.guaranteed_positions_by_operation:
            yield self.operations[operation]


@typing.final
class _ActionResolver:
    """Build the dependency interface of one reusable action."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        resolved_callees: Mapping[ast.GlobalTypedName, ResolvedAction],
    ):
        """Initialize resolution with one graph and its resolved direct callees."""
        self._graph = graph
        self._resolved_callees = resolved_callees

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Triggers."""
        operation_dependencies = self._resolve_operations()
        action_trigger_resolution = self._resolve_action_triggers()
        return self._build(operation_dependencies, action_trigger_resolution)

    def _build(
        self,
        operation_dependencies: dict[
            operation_graph_model.PositionOperationNode,
            tuple[ActionDependencies, list[CallerInput]],
        ],
        action_trigger_resolution: _ActionTriggerResolution,
    ) -> ResolvedAction:
        operations = self._build_operations(
            operation_dependencies,
            action_trigger_resolution,
        )
        return ResolvedAction(
            self._graph,
            operations,
            self._build_caller_inputs(
                operation_dependencies,
                action_trigger_resolution,
            ),
            ResolvedActionTriggers(
                action_trigger_resolution.action_triggers,
                action_trigger_resolution.destructor_triggers_by_guarantee,
            ),
        )

    @staticmethod
    def _build_caller_inputs(
        operation_dependencies: dict[
            operation_graph_model.PositionOperationNode,
            tuple[ActionDependencies, list[CallerInput]],
        ],
        action_trigger_resolution: _ActionTriggerResolution,
    ) -> list[CallerInput]:
        caller_inputs: dict[CallerInput, None] = {}
        for _, operation_caller_inputs in operation_dependencies.values():
            for caller_input in operation_caller_inputs:
                caller_inputs[caller_input] = None
        for resolved_trigger in action_trigger_resolution.action_triggers:
            for resolved_input in resolved_trigger.inputs:
                for caller_input in resolved_input.caller_input_dependencies:
                    caller_inputs[caller_input] = None
            if resolved_trigger.caller_input_dependency is not None:
                caller_inputs[resolved_trigger.caller_input_dependency] = None
        return list(caller_inputs)

    def _resolve_operations(
        self,
    ) -> dict[
        operation_graph_model.PositionOperationNode,
        tuple[ActionDependencies, list[CallerInput]],
    ]:
        operation_dependencies: dict[
            operation_graph_model.PositionOperationNode,
            tuple[ActionDependencies, list[CallerInput]],
        ] = {}
        for node in self._graph.nodes:
            if not isinstance(node, operation_graph_model.PositionOperationNode):
                continue
            operation_dependencies[node] = _partition_dependencies(node.depends_on)
        return operation_dependencies

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
        destructor_triggers_by_guarantee: dict[
            operation_graph_model.GuaranteeNode,
            list[ResolvedActionTrigger],
        ] = {}
        for trigger in self._graph.triggers:
            resolved_trigger = self._resolve_action_trigger(trigger)
            action_triggers.append(resolved_trigger)
            for resolved_input in resolved_trigger.inputs:
                for operation in resolved_input.caller_dependencies.local_operations:
                    triggered_inputs_by_operation.setdefault(operation, []).append(
                        resolved_input
                    )
            trigger_operation = trigger.trigger_operation
            if isinstance(
                trigger_operation, operation_graph_model.PositionOperationNode
            ):
                action_triggers_by_operation.setdefault(trigger_operation, []).append(
                    resolved_trigger
                )
            elif isinstance(trigger_operation, operation_graph_model.GuaranteeNode):
                destructor_triggers_by_guarantee.setdefault(
                    trigger_operation, []
                ).append(resolved_trigger)
        return _ActionTriggerResolution(
            action_triggers,
            triggered_inputs_by_operation,
            action_triggers_by_operation,
            destructor_triggers_by_guarantee,
        )

    def _build_operations(
        self,
        operation_dependencies: dict[
            operation_graph_model.PositionOperationNode,
            tuple[ActionDependencies, list[CallerInput]],
        ],
        action_trigger_resolution: _ActionTriggerResolution,
    ) -> dict[operation_graph_model.PositionOperationNode, ResolvedActionOperation]:
        operations: dict[
            operation_graph_model.PositionOperationNode, ResolvedActionOperation
        ] = {}
        for operation, (
            dependencies,
            caller_inputs,
        ) in operation_dependencies.items():
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
            operations[operation] = ResolvedActionOperation(
                operation,
                dependencies,
                self._graph.guaranteed_positions_by_operation.get(operation, ()),
                caller_inputs,
                triggered_inputs,
                action_triggers,
            )
        return operations

    def _resolve_action_trigger(
        self, trigger: operation_graph_model.ActionTrigger
    ) -> ResolvedActionTrigger:
        callee = self._resolved_callees[trigger.callee_action_name]
        dependency_resolver = _ActionTriggerDependencyResolver(self._graph, trigger)
        inputs: list[ResolvedActionTriggerInput] = []
        for callee_input in callee.caller_inputs:
            caller_dependencies, caller_input_dependencies = (
                dependency_resolver.resolve_input(callee_input)
            )
            resolved_input = ResolvedActionTriggerInput(
                callee_input,
                caller_dependencies,
                caller_input_dependencies,
            )
            inputs.append(resolved_input)
        trigger_operation = trigger.trigger_operation
        caller_input_dependency = None
        if isinstance(trigger_operation, operation_graph_model.RequirementNode):
            # The destructor might not act on an implied position, so resolving its
            # inputs does not necessarily discover this dependency.
            caller_input_dependency = trigger_operation
        return ResolvedActionTrigger(
            trigger,
            inputs,
            caller_input_dependency,
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
            self._operation_graphs[action], self._resolved
        ).resolve()
        self._resolved[action] = resolved
        return resolved

    def __getitem__(self, action: ast.GlobalTypedName) -> ResolvedAction:
        """Return a resolved action."""
        return self._resolved[action]
