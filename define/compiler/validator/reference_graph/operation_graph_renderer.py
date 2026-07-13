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
        caller_satisfiers: dict[tuple[str, ...], str | None] | None,
        dependencies: dict[str, list[str]],
    ) -> dict[int, str | None]:
        """Flatten ``action``, resolving each RequirementNode via ``caller_satisfiers``.

        ``caller_satisfiers`` maps this action's own requirement keys to the
        caller operations that satisfy them (None for the root action).
        """
        graph = self._registry[action]
        action_name = self._action_display_name(action)
        # The caller operation that satisfies this action's own trigger-position
        # requirement, which an operation with nothing else to wait on depends
        # on.
        trigger_label = (
            caller_satisfiers.get(graph.trigger_position_key)
            if caller_satisfiers
            else None
        )
        local_labels: dict[int, str | None] = {}
        # Keyed by (trigger operation id, callee action), for resolving the
        # guarantee nodes that stand in for the positions those callees
        # guarantee.
        callee_splices: dict[tuple[int, str], _CalleeSplice] = {}
        # Per trigger, the callee's requirement keys mapped to the label of the
        # operation that satisfies each, accumulated as each operation is
        # passed. An action can trigger one callee more than once, and each
        # trigger has its own satisfiers.
        satisfiers: dict[tuple[int, str], dict[tuple[str, ...], str | None]] = {}
        for node in graph.nodes:
            if isinstance(node, operation_graph.RequirementNode):
                # The caller operation that satisfies the requirement, found in
                # ``caller_satisfiers``; a required-EMPTY position no caller
                # operation satisfies falls through to whatever satisfies its
                # parent requirement, via its own depends_on.
                label = (
                    caller_satisfiers.get(node.requirement_position)
                    if caller_satisfiers
                    else None
                )
                if label is None:
                    label = next((local_labels[dep] for dep in node.depends_on), None)
                local_labels[node.node_id] = label
            elif isinstance(node, operation_graph.GuaranteeNode):
                # A position the callee guarantees: splice the callee (once)
                # and render the callee's final operation on that position.
                self._splice_trigger(
                    (node.depends_on[0], node.action),
                    satisfiers,
                    callee_splices,
                    dependencies,
                )
                local_labels[node.node_id] = self._final_operation_label(
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
                trigger = (satisfaction.trigger_node_id, callee)
                satisfiers.setdefault(trigger, {})[
                    satisfaction.requirement_position
                ] = local_labels[node.node_id]
        # A callee that guarantees nothing has no guarantee node to reach it,
        # and it still runs, so splice in every trigger not yet spliced.
        for trigger in sorted(satisfiers):
            self._splice_trigger(trigger, satisfiers, callee_splices, dependencies)
        return local_labels

    def _splice_trigger(
        self,
        trigger: tuple[int, str],
        satisfiers: dict[tuple[int, str], dict[tuple[str, ...], str | None]],
        callee_splices: dict[tuple[int, str], _CalleeSplice],
        dependencies: dict[str, list[str]],
    ):
        """Flatten the callee of ``trigger``, exactly once.

        Every satisfier of a trigger's requirements is an earlier operation than
        the callee's first guarantee node, so the callee is spliced with all of
        its satisfiers in hand.
        """
        if trigger in callee_splices:
            return
        _, callee = trigger
        callee_labels = self._flatten_action(callee, satisfiers[trigger], dependencies)
        callee_splices[trigger] = (self._registry[callee], callee_labels)

    def _final_operation_label(
        self,
        node: operation_graph.GuaranteeNode,
        callee_splices: dict[tuple[int, str], _CalleeSplice],
    ) -> str:
        trigger_node_id = node.depends_on[0]
        callee_graph, callee_labels = callee_splices[(trigger_node_id, node.action)]
        # A guaranteed position the callee only affected by moving an ancestor
        # resolves to that move.
        final_operation = callee_graph.last_operation_affecting_position(
            node.guaranteed_position
        )
        final_operation_label = callee_labels[final_operation]
        if final_operation_label is None:
            raise ValueError(
                f"unresolved final operation on {node.guaranteed_position} in {node.action}"
            )
        return final_operation_label

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
        # One edge per trigger: an action that fires the same callee twice
        # yields two edges. The operation that fires a trigger is the one that
        # satisfies the callee's requirement on its trigger position, so it is
        # the only satisfier whose satisfaction names itself.
        for node in graph.nodes:
            for satisfaction in node.satisfies:
                if satisfaction.trigger_node_id == node.node_id:
                    edges.append(
                        (source, satisfaction.callee.typed_names[-1].full_typed_name)
                    )
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
    operations are rendered under its own action prefix, and an operation with
    nothing else to wait on waits on the firing operation. A caller operation
    that reads a position a triggered action guarantees waits on that callee's
    final operation on the position. Every operation is keyed once (repeats of a
    label are suffixed ``#2``, ``#3``) and maps to what it waits on.
    """
    return _OperationGraphFlattener(program_result).flatten(root_action)
