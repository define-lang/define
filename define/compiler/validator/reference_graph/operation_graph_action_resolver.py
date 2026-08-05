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
        ItemsView,
        Iterable,
        Iterator,
        KeysView,
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
type _CallerInputDependency = (
    _CallerInputDependencyNode | operation_graph_model.CallerEmptyRuleDependencies
)


@dataclass(frozen=True, slots=True)
class ActionDependencies:
    """Dependencies resolved within one reusable action graph."""

    local_operations: list[operation_graph_model.PositionOperationNode]
    guarantee_dependencies: list[operation_graph_model.GuaranteeNode]


def _partition_dependencies(
    nodes: Iterable[operation_graph_model.OperationNode],
) -> tuple[ActionDependencies, list[_CallerInputDependency]]:
    """Separate local Particle Operations and guarantees from caller inputs."""
    local_operations: list[operation_graph_model.PositionOperationNode] = []
    guarantee_dependencies: list[operation_graph_model.GuaranteeNode] = []
    caller_input_dependencies: list[_CallerInputDependency] = []
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


@dataclass(slots=True, eq=False)
class ResolvedCallerInput:
    """A caller input and the operations, inputs, and destructors that consume it."""

    operation_consumers: list[operation_graph_model.PositionOperationNode] = field(
        default_factory=list, init=False
    )
    triggered_input_consumers: list[ResolvedActionTriggerInput] = field(
        default_factory=list, init=False
    )
    destructor_trigger_consumers: list[ResolvedActionTrigger] = field(
        default_factory=list, init=False
    )


@dataclass(slots=True, eq=False)
class ResolvedActionParentInput(ResolvedCallerInput):
    """An Action Parent input."""

    node: operation_graph_model.ActionParentLastOperationNode


@dataclass(slots=True, eq=False)
class ResolvedRequirementInput(ResolvedCallerInput):
    """A requirement input."""

    node: operation_graph_model.RequirementNode


@dataclass(slots=True, eq=False)
class ResolvedEmptyRuleInput(ResolvedCallerInput):
    """Empty Rule dependencies supplied by an action's caller."""

    dependencies: operation_graph_model.CallerEmptyRuleDependencies


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionTriggerInput:
    """One direct callee input resolved from the caller's perspective."""

    callee_input: ResolvedCallerInput
    caller_dependencies: ActionDependencies
    caller_input_dependencies: tuple[ResolvedCallerInput, ...]


@typing.final
class _ActionTriggerDependencyResolver:
    """Resolve a triggered action's caller inputs in its caller's operation graph."""

    def __init__(
        self,
        caller_graph: operation_graph.OperationGraph,
        trigger: operation_graph_model.ActionTrigger,
    ):
        """Initialize with one direct caller and Action Triggering."""
        self._caller_graph = caller_graph
        self._trigger = trigger

    def resolve_input(
        self, callee_input: ResolvedCallerInput
    ) -> tuple[ActionDependencies, list[_CallerInputDependency]]:
        """Return action-local dependencies and caller inputs for one callee input."""
        match callee_input:
            case ResolvedEmptyRuleInput():
                return self._resolve_caller_empty_rule_input(callee_input)
            case ResolvedActionParentInput() | ResolvedRequirementInput():
                return _partition_dependencies(
                    (self._caller_dependency_for_input_node(callee_input.node),)
                )
            case _:
                raise TypeError(
                    f"unknown caller input type: {type(callee_input).__name__}"
                )

    def _resolve_caller_empty_rule_input(
        self,
        callee_input: ResolvedEmptyRuleInput,
    ) -> tuple[ActionDependencies, list[_CallerInputDependency]]:
        """Resolve propagated Empty Rule dependencies into the direct caller."""
        substitution = self._caller_graph.substitute_caller_empty_rule_dependencies(
            callee_input.dependencies, self._trigger.bindings
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
    """The dependency interface of one direct Action Triggering."""

    trigger: operation_graph_model.ActionTrigger
    inputs: list[ResolvedActionTriggerInput]

    def input_for(
        self, callee_input: ResolvedCallerInput
    ) -> ResolvedActionTriggerInput:
        """Return the resolution of ``callee_input`` through this Action Triggering."""
        # This is inefficient but acceptable because this is used only by the
        # test-only resolved-operation-graph renderer.
        return next(
            resolved_input
            for resolved_input in self.inputs
            if resolved_input.callee_input is callee_input
        )


@typing.final
class ResolvedActionTriggers:
    """Resolved Action Triggerings and their reverse indexes."""

    def __init__(self):
        """Initialize an empty collection."""
        self._triggers: list[ResolvedActionTrigger] = []
        self._by_position_operation: dict[
            operation_graph_model.PositionOperationNode,
            list[ResolvedActionTrigger],
        ] = {}
        self._destructors_by_guarantee: dict[
            operation_graph_model.GuaranteeNode,
            list[ResolvedActionTrigger],
        ] = {}

    def __iter__(self) -> Iterator[ResolvedActionTrigger]:
        """Iterate over every resolved Action Triggering."""
        return iter(self._triggers)

    def __len__(self) -> int:
        """Return the number of resolved Action Triggerings."""
        return len(self._triggers)

    @property
    def position_operations(
        self,
    ) -> KeysView[operation_graph_model.PositionOperationNode]:
        """Return the Particle Operations that trigger actions."""
        return self._by_position_operation.keys()

    def by_position_operation(
        self,
    ) -> ItemsView[
        operation_graph_model.PositionOperationNode, list[ResolvedActionTrigger]
    ]:
        """Return Particle Operations and the Action Triggerings they cause."""
        return self._by_position_operation.items()

    def destructors_by_guarantee(
        self,
    ) -> ItemsView[operation_graph_model.GuaranteeNode, list[ResolvedActionTrigger]]:
        """Return guarantees and the destructors they trigger."""
        return self._destructors_by_guarantee.items()

    def add_operation(
        self,
        operation: operation_graph_model.LastOperationNode,
        trigger: ResolvedActionTrigger,
    ):
        """Add an Action Triggering caused by an operation."""
        self._triggers.append(trigger)
        if isinstance(operation, operation_graph_model.PositionOperationNode):
            self._by_position_operation.setdefault(operation, []).append(trigger)
        elif isinstance(operation, operation_graph_model.GuaranteeNode):
            self._destructors_by_guarantee.setdefault(operation, []).append(trigger)


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action."""

    graph: operation_graph.OperationGraph
    dependencies_by_operation: dict[
        operation_graph_model.PositionOperationNode, ActionDependencies
    ]
    caller_inputs: list[ResolvedCallerInput]
    action_triggers: ResolvedActionTriggers


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
        self._dependencies_by_operation: dict[
            operation_graph_model.PositionOperationNode, ActionDependencies
        ] = {}
        self._caller_inputs: list[ResolvedCallerInput] = []
        self._caller_input_by_node: dict[
            _CallerInputDependencyNode, ResolvedCallerInput
        ] = {}
        self._action_triggers = ResolvedActionTriggers()

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Triggerings."""
        for node in self._graph.nodes:
            if not isinstance(node, operation_graph_model.PositionOperationNode):
                continue
            self._dependencies_by_operation[node] = (
                self._resolve_operation_dependencies(node)
            )

        for trigger in self._graph.triggers:
            self._resolve_action_trigger(trigger)

        return ResolvedAction(
            self._graph,
            self._dependencies_by_operation,
            self._caller_inputs,
            self._action_triggers,
        )

    def _resolve_operation_dependencies(
        self, operation: operation_graph_model.PositionOperationNode
    ) -> ActionDependencies:
        dependencies, caller_input_dependencies = _partition_dependencies(
            operation.depends_on
        )
        self._record_operation_caller_inputs(caller_input_dependencies, operation)
        return dependencies

    def _resolve_action_trigger(self, trigger: operation_graph_model.ActionTrigger):
        callee = self._resolved_callees[trigger.callee_action_name]
        dependency_resolver = _ActionTriggerDependencyResolver(self._graph, trigger)
        inputs: list[ResolvedActionTriggerInput] = []
        for callee_input in callee.caller_inputs:
            caller_dependencies, caller_input_dependencies = (
                dependency_resolver.resolve_input(callee_input)
            )
            caller_inputs = tuple(
                self._caller_input_for(dependency)
                for dependency in caller_input_dependencies
            )
            resolved_input = ResolvedActionTriggerInput(
                callee_input, caller_dependencies, caller_inputs
            )
            inputs.append(resolved_input)
            for caller_input in caller_inputs:
                caller_input.triggered_input_consumers.append(resolved_input)
        resolved_trigger = ResolvedActionTrigger(trigger, inputs)
        trigger_operation = trigger.trigger_operation
        self._action_triggers.add_operation(trigger_operation, resolved_trigger)
        # This is a destructor triggering on a child of a from_caller particle.
        if isinstance(trigger_operation, operation_graph_model.RequirementNode):
            # There's no guarantee that resolving the destructor's operations resolved
            # the dependency on its parent, because the destructor might not have acted
            # on any implied positions. So we have to use _caller_input_for in case
            # we have to generate the resolved requirement node.
            caller_input = self._caller_input_for(trigger_operation)
            caller_input.destructor_trigger_consumers.append(resolved_trigger)
            caller_input.triggered_input_consumers.extend(resolved_trigger.inputs)

    def _record_operation_caller_inputs(
        self,
        caller_input_dependencies: list[_CallerInputDependency],
        operation: operation_graph_model.PositionOperationNode,
    ):
        for dependency in caller_input_dependencies:
            self._caller_input_for(dependency).operation_consumers.append(operation)

    def _caller_input_for(
        self, dependency: _CallerInputDependency
    ) -> ResolvedCallerInput:
        if isinstance(dependency, operation_graph_model.CallerEmptyRuleDependencies):
            caller_input = ResolvedEmptyRuleInput(dependency)
            self._caller_inputs.append(caller_input)
            return caller_input
        caller_input = self._caller_input_by_node.get(dependency)
        if caller_input is None:
            match dependency:
                case operation_graph_model.ActionParentLastOperationNode():
                    caller_input = ResolvedActionParentInput(dependency)
                case operation_graph_model.RequirementNode():
                    caller_input = ResolvedRequirementInput(dependency)
                case operation_graph_model.CallerEmptyRuleDependenciesNode():
                    caller_input = ResolvedEmptyRuleInput(
                        dependency.caller_empty_rule_dependencies
                    )
            self._caller_input_by_node[dependency] = caller_input
            self._caller_inputs.append(caller_input)
        return caller_input


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
