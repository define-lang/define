# pyright: reportUnusedCallResult=false
"""Renders DLP 44 operation graphs as readable adjacency dicts for tests."""

from collections import Counter
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import operation_graph

# For a spliced-in triggered action: its graph, and its node-id -> rendered label.
_CalleeSplice = tuple[operation_graph.OperationGraph, dict[int, str | None]]


@dataclass(frozen=True, slots=True)
class _CallerContext:
    """The caller-side scope a spliced callee resolves its RequirementNodes against."""

    graph: operation_graph.OperationGraph
    # The caller's node-id -> rendered label, live as the caller is flattened.
    labels: dict[int, str | None]
    # The caller operation that fired this callee.
    trigger_node_id: int
    # The callee's absolute chain in the caller (the trigger's action chain).
    callee_chain: tuple[str, ...]


class _OperationGraphFlattener:
    """Flattens an operation graph and any actions it triggers."""

    def __init__(self, program_result: validation_result.ProgramValidationResult):
        self._registry: dict[str, operation_graph.OperationGraph] = {
            typed_name.full_typed_name: definition_result.operation_graph
            for typed_name, definition_result in program_result.definition_results.items()
            if definition_result.operation_graph is not None
        }
        self._label_counts: Counter[str] = Counter()

    def flatten(self, root_action: str) -> dict[str, list[str]]:
        """Map each operation to the operations it waits on."""
        dependencies: dict[str, list[str]] = {}
        self._flatten_action(root_action, None, None, dependencies)
        return dependencies

    def _flatten_action(
        self,
        action: str,
        trigger_label: str | None,
        caller_context: _CallerContext | None,
        dependencies: dict[str, list[str]],
    ) -> dict[int, str | None]:
        graph = self._registry[action]
        action_name = self._action_display_name(action)
        local_labels: dict[int, str | None] = {}
        # Keyed by (trigger operation id, callee action), for resolving the
        # guarantee nodes that stand in for those callees' outputs.
        callee_splices: dict[tuple[int, str], _CalleeSplice] = {}
        for node in graph.nodes:
            if isinstance(node, operation_graph.RequirementNode):
                # A seam for the caller op that satisfies the requirement: the
                # caller op on this exact position, or -- for a position the caller
                # never touched (an empty-by-default child) -- whatever satisfies
                # its parent requirement, reached through its own depends_on.
                label = self._requirement_caller_label(node, caller_context)
                if label is None:
                    label = next((local_labels[dep] for dep in node.depends_on), None)
                local_labels[node.node_id] = label
                continue
            if isinstance(node, operation_graph.GuaranteeNode):
                # A callee output: it renders as the callee's own split point.
                local_labels[node.node_id] = self._split_point_label(
                    node, callee_splices
                )
                continue
            label = self._operation_label(action_name, node)
            predecessors = [
                resolved
                for dep in node.depends_on
                if (resolved := local_labels[dep]) is not None
            ]
            # An operation whose only dependencies were RequirementNodes with no
            # satisfying caller op still waits on the trigger, so it runs after
            # the callee's context exists.
            if not predecessors and trigger_label is not None:
                predecessors = [trigger_label]
            dependencies[label] = predecessors
            local_labels[node.node_id] = label
            for triggered in graph.triggered_actions(node.node_id):
                callee_action = triggered.typed_names[-1].full_typed_name
                child_context = _CallerContext(
                    graph=graph,
                    labels=local_labels,
                    trigger_node_id=node.node_id,
                    callee_chain=triggered.canonical_chained_name_tuple,
                )
                callee_labels = self._flatten_action(
                    callee_action, label, child_context, dependencies
                )
                callee_splices[(node.node_id, callee_action)] = (
                    self._registry[callee_action],
                    callee_labels,
                )
        return local_labels

    def _requirement_caller_label(
        self,
        node: operation_graph.RequirementNode,
        caller_context: _CallerContext | None,
    ) -> str | None:
        """Resolve a RequirementNode to the caller op that most recently operated on its exact position before the trigger.

        Ancestor positions are handled by the node's own ``depends_on`` (its parent
        RequirementNode), not here. The root action's own requirements are program
        inputs with no caller, so they resolve to nothing.
        """
        # TODO: This only resolves against the immediate caller. A requirement
        # that propagates up several call levels is satisfied by an op further
        # up the stack, so we need to re-propagate the callee's RequirementNodes
        # into each caller (as we do guarantees) and resolve there. The
        # test_occupied_requirement_two_levels_up_* tests are xfail on this.
        if caller_context is None:
            return None
        requirement_key = node.caller_key(caller_context.callee_chain)
        best_node_id: int | None = None
        for caller_node in caller_context.graph.nodes:
            if caller_node.node_id >= caller_context.trigger_node_id:
                continue
            if requirement_key in self._touched_keys(caller_node) and (
                best_node_id is None or caller_node.node_id > best_node_id
            ):
                best_node_id = caller_node.node_id
        if best_node_id is None:
            return None
        return caller_context.labels[best_node_id]

    def _touched_keys(
        self, node: operation_graph.OperationNode
    ) -> tuple[tuple[str, ...], ...]:
        """Return the position keys an operation reads or writes, in any role."""
        match node:
            case operation_graph.CreateNode() | operation_graph.DestroyNode():
                return (node.target.canonical_chained_name_tuple,)
            case operation_graph.MoveNode():
                return (
                    node.source.canonical_chained_name_tuple,
                    node.target.canonical_chained_name_tuple,
                )
            case _:
                return ()

    def _split_point_label(
        self,
        node: operation_graph.GuaranteeNode,
        callee_splices: dict[tuple[int, str], _CalleeSplice],
    ) -> str:
        trigger_node_id = node.depends_on[0]
        callee_graph, callee_labels = callee_splices[(trigger_node_id, node.action)]
        split_point = callee_graph.last_operation_node_id_for_key(node.output_position)
        if split_point is None:
            raise ValueError(
                f"no split point for {node.output_position} in {node.action}"
            )
        split_point_label = callee_labels[split_point]
        if split_point_label is None:
            raise ValueError(
                f"unresolved split point for {node.output_position} in {node.action}"
            )
        return split_point_label

    def _operation_label(
        self, action_name: str, node: operation_graph.OperationNode
    ) -> str:
        match node:
            case operation_graph.CreateNode():
                label = f"{action_name}.create({self._short_chained_name(node.target)})"
            case operation_graph.DestroyNode():
                label = (
                    f"{action_name}.destroy({self._short_chained_name(node.target)})"
                )
            case operation_graph.MoveNode():
                source = self._short_chained_name(node.source)
                label = f"{action_name}.move({source}, {self._short_chained_name(node.target)})"
            case _:
                raise TypeError(f"unexpected operation node {type(node).__name__}")
        return self._disambiguated(label)

    def _short_chained_name(self, reference: ast.PositionReference) -> str:
        return "::".join(
            element.name_content.source_name for element in reference.typed_names
        )

    def _action_display_name(self, action_full_typed_name: str) -> str:
        inner = action_full_typed_name[
            action_full_typed_name.index("<") + 1 : action_full_typed_name.rindex(">")
        ]
        return inner.rsplit(":", 1)[-1].lstrip("/")

    def _disambiguated(self, label: str) -> str:
        self._label_counts[label] += 1
        count = self._label_counts[label]
        return label if count == 1 else f"{label}#{count}"


def action_graph(
    program_result: validation_result.ProgramValidationResult,
) -> list[tuple[str, str]]:
    """Return each action's directly-triggered actions as (source, target) name pairs.

    Actions appear in reference-graph post-order and their triggers in
    body-operation order, so the result is deterministic. A reference-graph
    diamond can still make two sibling actions' relative order nondeterministic;
    assertions spanning such actions should compare ``action_graph_set``.
    """
    edges: list[tuple[str, str]] = []
    for definition in program_result.reference_graph.dfs_postorder_all():
        typed_name = definition.typed_name
        if typed_name not in program_result.definition_results:
            continue
        graph = program_result.definition_results[typed_name].operation_graph
        if graph is None:
            continue
        source = typed_name.source_typed_name
        for node in graph.nodes:
            for action_ref in graph.triggered_actions(node.node_id):
                edges.append((source, action_ref.typed_names[-1].full_typed_name))
    return edges


def action_graph_set(
    program_result: validation_result.ProgramValidationResult,
) -> set[tuple[str, str]]:
    """Return ``action_graph`` as a set, for assertions whose edge order is nondeterministic."""
    return set(action_graph(program_result))


def operation_dependencies(
    program_result: validation_result.ProgramValidationResult,
    root_action: str,
) -> dict[str, list[str]]:
    """Map each operation of ``root_action`` (and the actions it triggers) to what it waits on.

    A triggered action is spliced in at the operation that fires it: its
    operations are rendered under its own action prefix and its roots wait on the
    firing operation. A caller operation that reads a triggered action's output
    waits on that callee's own split point. Every operation is keyed once
    (repeats of a label are suffixed ``#2``, ``#3``) and maps to what it waits on.
    """
    return _OperationGraphFlattener(program_result).flatten(root_action)
