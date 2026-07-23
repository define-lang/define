"""Resolves symbolic dependencies between per-action operation graphs."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler.validator.reference_graph import operation_graph

# Resolution must be limited to substitutions that codegen can perform while
# consuming an operation graph. Operation graphs must already contain the
# correct minimal direct dependencies; resolution must never compensate for
# missing graph-construction information by analyzing or repairing the resolved
# graph.

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from define.compiler import ast


type CallerInputNode = (
    operation_graph.ActionParentLastOperationNode
    | operation_graph.RequirementNode
    | operation_graph.CallerEmptyRuleDependenciesNode
)
type ActionInput = CallerInputNode | operation_graph.CallerEmptyRuleDependencies


@dataclass(frozen=True, slots=True)
class ActionDependencies:
    """Dependencies of an operation in one reusable action graph."""

    local_operation_node_ids: tuple[int, ...] = ()
    action_inputs: tuple[ActionInput, ...] = ()
    guarantee_dependencies: tuple[operation_graph.GuaranteeNode, ...] = ()

    @classmethod
    def for_nodes(
        cls, nodes: Iterable[operation_graph.OperationNode]
    ) -> ActionDependencies:
        """Create dependencies for a list of operation-graph nodes."""
        dependencies = _ActionDependenciesBuilder()
        for node in nodes:
            dependencies.add_dependency(node)
        return dependencies.build()


class _ActionDependenciesBuilder:
    """Collect action dependencies in graph order."""

    def __init__(self):
        self.local_operation_node_ids: list[int] = []
        self.action_inputs: list[ActionInput] = []
        self.guarantee_dependencies: list[operation_graph.GuaranteeNode] = []

    def add_dependency(self, node: operation_graph.OperationNode):
        match node:
            case operation_graph.PositionOperationNode():
                self.local_operation_node_ids.append(node.node_id)
            case (
                operation_graph.ActionParentLastOperationNode()
                | operation_graph.RequirementNode()
                | operation_graph.CallerEmptyRuleDependenciesNode()
            ):
                self.action_inputs.append(node)
            case operation_graph.GuaranteeNode():
                self.guarantee_dependencies.append(node)
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    def build(self) -> ActionDependencies:
        """Build immutable dependencies in graph order."""
        return ActionDependencies(
            local_operation_node_ids=tuple(self.local_operation_node_ids),
            action_inputs=tuple(self.action_inputs),
            guarantee_dependencies=tuple(self.guarantee_dependencies),
        )


@dataclass(frozen=True, slots=True)
class ResolvedActionTriggerInput:
    """One direct callee input resolved from the caller's perspective."""

    callee_input: ActionInput
    caller_dependencies: ActionDependencies
    callee_dependency_node_ids: tuple[int, ...]


@typing.final
class _ActionTriggerDependencyResolver:
    """Resolve a triggered action's caller inputs in its caller's operation graph."""

    def __init__(
        self,
        caller_graph: operation_graph.OperationGraph,
        callee_graph: operation_graph.OperationGraph,
        trigger: operation_graph.ActionTrigger,
    ):
        """Initialize with one direct caller, triggered action, and ActionTrigger."""
        self._caller_graph = caller_graph
        self._callee_graph = callee_graph
        self._trigger = trigger

    def action_parent_operation(self) -> operation_graph.OperationNode:
        """Return the caller operation on the triggered action's parent position."""
        return self._caller_graph.nodes[
            self._trigger.action_parent_last_operation_node_id
        ]

    def bound_requirement_operation(
        self, requirement: operation_graph.RequirementNode
    ) -> operation_graph.OperationNode | None:
        """Return the caller operation bound to ``requirement``.

        ``None`` means an empty requirement is satisfied because the position
        is empty by default.
        """
        binding = self._trigger.bindings.get(requirement.requirement_position)
        if binding is None:
            return None
        return self._caller_graph.nodes[binding.node_id]

    def empty_by_default_parent_operations(
        self, requirement: operation_graph.RequirementNode
    ) -> Iterable[operation_graph.OperationNode]:
        """Return callee parent operations preceding an empty-by-default requirement."""
        return (self._callee_graph.nodes[node_id] for node_id in requirement.depends_on)

    def substitute_empty_rule_dependencies(
        self, node: operation_graph.CallerEmptyRuleDependenciesNode
    ) -> operation_graph.CallerEmptyRuleSubstitution:
        """Substitute caller bindings into one callee Empty Rule dependency set."""
        return self._caller_graph.substitute_caller_empty_rule_dependencies(
            node.caller_empty_rule_dependencies, self._trigger.bindings
        )

    def resolve_input(self, callee_input: ActionInput) -> ResolvedActionTriggerInput:
        """Resolve a triggered action's input from the caller's perspective."""
        match callee_input:
            case operation_graph.CallerEmptyRuleDependencies():
                return self._resolve_caller_empty_rule_input(callee_input)
            case (
                operation_graph.ActionParentLastOperationNode()
                | operation_graph.RequirementNode()
                | operation_graph.CallerEmptyRuleDependenciesNode()
            ):
                return self._resolve_input_node(callee_input)

    def _resolve_input_node(self, node: CallerInputNode) -> ResolvedActionTriggerInput:
        dependencies = _ActionDependenciesBuilder()
        callee_dependency_node_ids: list[int] = []
        self._add_input_node(dependencies, callee_dependency_node_ids, node)
        return ResolvedActionTriggerInput(
            node,
            dependencies.build(),
            tuple(callee_dependency_node_ids),
        )

    def _resolve_caller_empty_rule_input(
        self,
        caller_empty_rule_dependencies: operation_graph.CallerEmptyRuleDependencies,
    ) -> ResolvedActionTriggerInput:
        """Resolve propagated Empty Rule dependencies into the direct caller."""
        substitution = self._caller_graph.substitute_caller_empty_rule_dependencies(
            caller_empty_rule_dependencies, self._trigger.bindings
        )
        dependencies = _ActionDependenciesBuilder()
        self._add_empty_rule_substitution(dependencies, substitution)
        return ResolvedActionTriggerInput(
            caller_empty_rule_dependencies,
            dependencies.build(),
            (),
        )

    def _add_input_node(
        self,
        dependencies: _ActionDependenciesBuilder,
        callee_dependency_node_ids: list[int],
        node: CallerInputNode,
    ):
        match node:
            case operation_graph.ActionParentLastOperationNode():
                dependencies.add_dependency(self.action_parent_operation())
            case operation_graph.RequirementNode():
                operation = self.bound_requirement_operation(node)
                if operation is not None:
                    dependencies.add_dependency(operation)
                    return
                for parent_operation in self.empty_by_default_parent_operations(node):
                    if isinstance(
                        parent_operation,
                        (
                            operation_graph.ActionParentLastOperationNode,
                            operation_graph.RequirementNode,
                            operation_graph.CallerEmptyRuleDependenciesNode,
                        ),
                    ):
                        self._add_input_node(
                            dependencies,
                            callee_dependency_node_ids,
                            parent_operation,
                        )
                    else:
                        callee_dependency_node_ids.append(parent_operation.node_id)
            case operation_graph.CallerEmptyRuleDependenciesNode():
                self._add_empty_rule_substitution(
                    dependencies, self.substitute_empty_rule_dependencies(node)
                )

    def _add_empty_rule_substitution(
        self,
        dependencies: _ActionDependenciesBuilder,
        substitution: operation_graph.CallerEmptyRuleSubstitution,
    ):
        for node in substitution.dependency_nodes:
            dependencies.add_dependency(node)
        if substitution.caller_empty_rule_dependencies is not None:
            dependencies.action_inputs.append(
                substitution.caller_empty_rule_dependencies
            )


@dataclass(frozen=True, slots=True)
class ResolvedActionTrigger:
    """The dependency interface of one direct Action Triggering."""

    trigger: operation_graph.ActionTrigger
    inputs: tuple[ResolvedActionTriggerInput, ...]

    def input_for(self, callee_input: ActionInput) -> ResolvedActionTriggerInput:
        """Return the resolution of ``callee_input`` through this Action Triggering."""
        return next(
            resolved_input
            for resolved_input in self.inputs
            if resolved_input.callee_input is callee_input
        )


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """The dependency interface of one reusable action."""

    graph: operation_graph.OperationGraph
    dependencies_by_operation_node_id: dict[int, ActionDependencies]
    inputs: tuple[ActionInput, ...]
    action_triggers: tuple[ResolvedActionTrigger, ...]


@typing.final
class ActionResolver:
    """Build the dependency interface of one reusable action."""

    def __init__(
        self,
        graph: operation_graph.OperationGraph,
        resolved_actions: Mapping[ast.GlobalTypedName, ResolvedAction],
    ):
        """Initialize resolution with one graph and its resolved direct callees."""
        self._graph = graph
        self._resolved_actions = resolved_actions
        self._dependencies_by_operation_node_id: dict[int, ActionDependencies] = {}
        self._inputs: list[ActionInput] = []
        self._caller_input_node_ids: set[int] = set()
        self._action_triggers: list[ResolvedActionTrigger] = []

    def resolve(self) -> ResolvedAction:
        """Resolve the action's operations and direct Action Triggerings."""
        for node in self._graph.nodes:
            if not isinstance(node, operation_graph.PositionOperationNode):
                continue
            dependencies = ActionDependencies.for_nodes(
                self._graph.nodes[node_id] for node_id in node.depends_on
            )
            self._dependencies_by_operation_node_id[node.node_id] = dependencies
            self._record_caller_dependencies(dependencies)

        for trigger in self._graph.triggers:
            self._action_triggers.append(self._resolve_action_trigger(trigger))

        return ResolvedAction(
            self._graph,
            self._dependencies_by_operation_node_id,
            tuple(self._inputs),
            tuple(self._action_triggers),
        )

    def _resolve_action_trigger(
        self, trigger: operation_graph.ActionTrigger
    ) -> ResolvedActionTrigger:
        callee = self._resolved_actions[trigger.callee_action_name]
        dependency_resolver = _ActionTriggerDependencyResolver(
            self._graph, callee.graph, trigger
        )
        inputs: list[ResolvedActionTriggerInput] = []
        for callee_input in callee.inputs:
            resolved_input = dependency_resolver.resolve_input(callee_input)
            inputs.append(resolved_input)
            self._record_caller_dependencies(resolved_input.caller_dependencies)
        return ResolvedActionTrigger(trigger, tuple(inputs))

    def _record_caller_dependencies(self, dependencies: ActionDependencies):
        for action_input in dependencies.action_inputs:
            if isinstance(action_input, operation_graph.CallerEmptyRuleDependencies):
                self._inputs.append(action_input)
            elif action_input.node_id not in self._caller_input_node_ids:
                self._caller_input_node_ids.add(action_input.node_id)
                self._inputs.append(action_input)
