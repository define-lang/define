# pyright: reportUnusedCallResult=false
"""Renders DLP 44 operation graphs as readable adjacency dicts for tests."""

from collections import Counter

from define.compiler import ast
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import operation_graph

# For a spliced-in triggered action: its graph, and its node-id -> rendered label.
_CalleeSplice = tuple[operation_graph.OperationGraph, dict[int, str | None]]


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
        self._flatten_action(root_action, None, dependencies)
        return dependencies

    def _flatten_action(
        self,
        action: str,
        satisfiers: dict[tuple[str, ...], str | None] | None,
        dependencies: dict[str, list[str]],
    ) -> dict[int, str | None]:
        """Flatten ``action``, resolving each RequirementNode via ``satisfiers``.

        ``satisfiers`` maps this action's own requirement keys to the caller
        operations that satisfy them (None for the root action).
        """
        graph = self._registry[action]
        action_name = self._action_display_name(action)
        # The caller operation that satisfies this action's own trigger-position
        # requirement, which an operation with nothing else to wait on depends
        # on.
        trigger_label = (
            satisfiers.get(graph.trigger_position_key) if satisfiers else None
        )
        local_labels: dict[int, str | None] = {}
        # Keyed by (trigger operation id, callee action), for resolving the
        # guarantee nodes that stand in for those callees' outputs.
        callee_splices: dict[tuple[int, str], _CalleeSplice] = {}
        # (callee full typed name, callee requirement key) -> label of the
        # operation that satisfies it, accumulated as each operation is passed.
        outgoing: dict[tuple[str, tuple[str, ...]], str | None] = {}
        for node in graph.nodes:
            if isinstance(node, operation_graph.RequirementNode):
                # A seam for the caller op that satisfies the requirement, found in
                # ``satisfiers``; an untouched empty-by-default position falls
                # through to whatever satisfies its parent, via its own depends_on.
                label = (
                    satisfiers.get(node.requirement_position) if satisfiers else None
                )
                if label is None:
                    label = next((local_labels[dep] for dep in node.depends_on), None)
                local_labels[node.node_id] = label
            elif isinstance(node, operation_graph.GuaranteeNode):
                # A callee output: splice the callee (once) and render its own
                # split point.
                self._splice_callee(node, outgoing, callee_splices, dependencies)
                local_labels[node.node_id] = self._split_point_label(
                    node, callee_splices
                )
            else:
                label = self._operation_label(action_name, node)
                predecessors = [
                    resolved
                    for dep in node.depends_on
                    if (resolved := local_labels[dep]) is not None
                ]
                # An operation whose requirements all hold by default has no
                # satisfying caller op to wait on, so it waits on the
                # trigger-position requirement's satisfier: it runs once the
                # callee's context exists.
                if not predecessors and trigger_label is not None:
                    predecessors = [trigger_label]
                dependencies[label] = predecessors
                local_labels[node.node_id] = label
            for satisfaction in node.satisfies:
                callee = satisfaction.callee.typed_names[-1].full_typed_name
                outgoing[(callee, satisfaction.requirement_position)] = local_labels[
                    node.node_id
                ]
        return local_labels

    def _splice_callee(
        self,
        guarantee_node: operation_graph.GuaranteeNode,
        outgoing: dict[tuple[str, tuple[str, ...]], str | None],
        callee_splices: dict[tuple[int, str], _CalleeSplice],
        dependencies: dict[str, list[str]],
    ):
        """Flatten the callee this guarantee comes from, once per (trigger, callee)."""
        callee = guarantee_node.action
        trigger_node_id = guarantee_node.depends_on[0]
        if (trigger_node_id, callee) in callee_splices:
            return
        satisfiers = {
            requirement_position: label
            for (satisfied_callee, requirement_position), label in outgoing.items()
            if satisfied_callee == callee
        }
        callee_labels = self._flatten_action(callee, satisfiers, dependencies)
        callee_splices[(trigger_node_id, callee)] = (
            self._registry[callee],
            callee_labels,
        )

    def _split_point_label(
        self,
        node: operation_graph.GuaranteeNode,
        callee_splices: dict[tuple[int, str], _CalleeSplice],
    ) -> str:
        trigger_node_id = node.depends_on[0]
        callee_graph, callee_labels = callee_splices[(trigger_node_id, node.action)]
        # A guaranteed output the callee only operated on by moving an ancestor
        # resolves to that move.
        split_point = callee_graph.last_operation_affecting_position(
            node.output_position
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
    registry: dict[str, operation_graph.OperationGraph] = {
        typed_name.full_typed_name: definition_result.operation_graph
        for typed_name, definition_result in program_result.definition_results.items()
        if definition_result.operation_graph is not None
    }
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
            for satisfaction in node.satisfies:
                callee = satisfaction.callee.typed_names[-1].full_typed_name
                callee_graph = registry.get(callee)
                # The firing satisfaction is keyed to the callee's trigger position
                # (or its root for a constructor); an inferred-requirement
                # satisfaction never is, since the trigger is excluded from
                # requirements. So this counts one edge per trigger -- an action
                # that fires the same callee twice yields two edges.
                firing_key = (
                    callee_graph.trigger_position_key
                    if callee_graph is not None
                    else ()
                )
                if satisfaction.requirement_position == firing_key:
                    edges.append((source, callee))
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
