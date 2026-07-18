"""Resolves symbolic dependencies between per-action operation graphs."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import operation_graph

# Resolution must be limited to substitutions that codegen can perform while
# consuming an operation graph. Operation graphs must already contain the
# correct minimal direct dependencies; resolution must never compensate for
# missing graph-construction information by analyzing or repairing the resolved
# graph.

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

type OperationGraphs = typed_name_dict.TypedNameDict[
    ast.GlobalTypedName, operation_graph.OperationGraph
]


@dataclass(frozen=True, slots=True, eq=False)
class TriggeredBy:
    """The trigger and caller that created an action instance."""

    caller: ResolvedActionInstance
    trigger: operation_graph.ActionTrigger


@dataclass(frozen=True, slots=True, eq=False)
class ResolvedActionInstance:
    """One instance of an action in the graph expanded from the entry action."""

    action: ast.GlobalTypedName
    triggered_by: TriggeredBy | None


@dataclass(frozen=True, slots=True)
class ResolvedNodeId:
    """The identity of a node in one action instance."""

    action_instance: ResolvedActionInstance
    node_id: int


@typing.final
class ResolvedOperationGraph:
    """A self-contained resolved view of all operations reached from one action."""

    def __init__(
        self,
        graphs: OperationGraphs,
        callee_action_instances: dict[
            tuple[ResolvedActionInstance, int], ResolvedActionInstance
        ],
        entry_action_instance: ResolvedActionInstance,
        nodes: list[ResolvedNodeId],
    ):
        """Store the already-resolved action instances and operation nodes."""
        self._graphs = graphs
        self._callee_action_instances = callee_action_instances
        self._entry_action_instance = entry_action_instance
        self._nodes = nodes
        self._dependency_cache: dict[ResolvedNodeId, tuple[ResolvedNodeId, ...]] = {}

    @classmethod
    def from_graphs(
        cls, graphs: OperationGraphs, entry_action: ast.GlobalTypedName
    ) -> ResolvedOperationGraph:
        """Resolve the full graph of operations reachable from ``entry_action``."""
        callee_action_instances: dict[
            tuple[ResolvedActionInstance, int], ResolvedActionInstance
        ] = {}
        nodes: list[ResolvedNodeId] = []
        root = ResolvedActionInstance(entry_action, triggered_by=None)
        work: list[ResolvedActionInstance] = [root]
        while work:
            action_instance = work.pop()
            graph = graphs[action_instance.action]
            nodes.extend(
                ResolvedNodeId(action_instance, node.node_id)
                for node in graph.nodes
                if isinstance(node, operation_graph.PositionOperationNode)
            )
            callees = [
                ResolvedActionInstance(
                    trigger.callee_action_name,
                    TriggeredBy(action_instance, trigger),
                )
                for trigger in graph.triggers
            ]
            for callee in callees:
                triggered_by = callee.triggered_by
                if triggered_by is not None:
                    callee_action_instances[
                        (action_instance, id(triggered_by.trigger))
                    ] = callee
            work.extend(reversed(callees))
        return cls(graphs, callee_action_instances, root, nodes)

    @property
    def entry_action_instance(self) -> ResolvedActionInstance:
        """Return the instance of the action resolution started from."""
        return self._entry_action_instance

    @property
    def nodes(self) -> Iterable[ResolvedNodeId]:
        """Return concrete operation nodes in deterministic action-instance order."""
        return self._nodes

    def operation(
        self, resolved: ResolvedNodeId
    ) -> operation_graph.PositionOperationNode:
        """Return the concrete operation identified by ``resolved``."""
        return typing.cast(
            "operation_graph.PositionOperationNode",
            self._graphs[resolved.action_instance.action].nodes[resolved.node_id],
        )

    def dependencies(self, node: ResolvedNodeId) -> Iterable[ResolvedNodeId]:
        """Return the concrete operations that ``node`` directly waits on."""
        cached = self._dependency_cache.get(node)
        if cached is None:
            action_instance = node.action_instance
            local_node = self.operation(node)
            resolved = self._resolve_ids(action_instance, local_node.depends_on)
            # Multiple symbolic paths can reach the same operation. Cache the
            # ordered unique result as a tuple so callers cannot mutate it.
            cached = tuple(dict.fromkeys(resolved))
            self._dependency_cache[node] = cached
        return cached

    def _resolve_ids(
        self, action_instance: ResolvedActionInstance, node_ids: Iterable[int]
    ) -> list[ResolvedNodeId]:
        result: list[ResolvedNodeId] = []
        for node_id in node_ids:
            result.extend(self._resolve_node(action_instance, node_id))
        return result

    def _resolve_node(
        self, action_instance: ResolvedActionInstance, node_id: int
    ) -> list[ResolvedNodeId]:
        graph = self._graphs[action_instance.action]
        node = graph.nodes[node_id]
        match node:
            case operation_graph.ActionParentLastOperationNode():
                if action_instance.triggered_by is None:
                    return []
                return self._resolve_node(
                    action_instance.triggered_by.caller,
                    action_instance.triggered_by.trigger.action_parent_last_operation_node_id,
                )
            case operation_graph.PositionOperationNode():
                return [ResolvedNodeId(action_instance, node_id)]
            case operation_graph.RequirementNode():
                return self._resolve_requirement(action_instance, node)
            case operation_graph.CallerDependenciesNode():
                return self._resolve_caller_dependencies(
                    action_instance, node.caller_dependencies
                )
            case operation_graph.GuaranteeNode():
                callee = self._callee_instance(action_instance, node.trigger)
                return self._resolve_guaranteed_position(
                    callee, node.guaranteed_position
                )
            case _:
                raise TypeError(f"unknown operation node type: {type(node).__name__}")

    def _resolve_guaranteed_position(
        self,
        action_instance: ResolvedActionInstance,
        position: tuple[str, ...],
    ) -> list[ResolvedNodeId]:
        """Resolve a guarantee attached to requirements across action instances."""
        while True:
            graph = self._graphs[action_instance.action]
            node_id = graph.last_operation_on_position(position)
            node = graph.nodes[node_id]
            if not isinstance(node, operation_graph.RequirementNode):
                return self._resolve_node(action_instance, node_id)
            guarantee_trigger = graph.last_trigger_using_requirement(node.node_id)
            position = ast.chain_in_callee(guarantee_trigger.action_chain, position)
            action_instance = self._callee_instance(action_instance, guarantee_trigger)

    def _resolve_requirement(
        self,
        action_instance: ResolvedActionInstance,
        node: operation_graph.RequirementNode,
    ) -> list[ResolvedNodeId]:
        if action_instance.triggered_by is None:
            return []
        binding = action_instance.triggered_by.trigger.bindings.get(
            node.requirement_position
        )
        if binding is not None:
            return self._resolve_node(
                action_instance.triggered_by.caller, binding.node_id
            )
        return self._resolve_ids(action_instance, node.depends_on)

    def _resolve_caller_dependencies(
        self,
        action_instance: ResolvedActionInstance,
        caller_dependencies: operation_graph.CallerDependencies,
    ) -> list[ResolvedNodeId]:
        triggered_by = action_instance.triggered_by
        if triggered_by is None:
            return []
        caller = triggered_by.caller
        caller_graph = self._graphs[caller.action]
        substitution = caller_graph.substitute_caller_dependencies(
            caller_dependencies, triggered_by.trigger.bindings
        )
        dependencies = self._resolve_ids(caller, substitution.node_ids)
        if substitution.caller_dependencies is not None:
            dependencies.extend(
                self._resolve_caller_dependencies(
                    caller, substitution.caller_dependencies
                )
            )
        return dependencies

    def _callee_instance(
        self,
        action_instance: ResolvedActionInstance,
        trigger: operation_graph.ActionTrigger,
    ) -> ResolvedActionInstance:
        return self._callee_action_instances[(action_instance, id(trigger))]
