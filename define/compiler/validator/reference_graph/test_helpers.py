# pyright: reportUnusedCallResult=false
"""Shared helpers for tests that inspect post-order validation results."""

import collections
from unittest import mock

from define.compiler import ast
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
    operation_graph,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator
from define.compiler.validator.test_helpers import assert_no_errors


def _short_chained_name(reference: ast.PositionReference) -> str:
    """Render a position reference as its bare ``::``-joined names, without the type wrappers."""
    return "::".join(
        element.name_content.source_name for element in reference.typed_names
    )


def _action_display_name(action_full_typed_name: str) -> str:
    """Render an action's full typed name as its bare path, e.g. ``test`` for ``action<...:/test>``."""
    inner = action_full_typed_name[
        action_full_typed_name.index("<") + 1 : action_full_typed_name.rindex(">")
    ]
    return inner.rsplit(":", 1)[-1].lstrip("/")


def _render_operation(action_name: str, node: operation_graph.OperationNode) -> str:
    """Render one operation node as ``action.kind(target)`` (or ``action.move(source, target)``)."""
    target = _short_chained_name(node.target)
    match node.kind:
        case operation_graph.OperationKind.CREATE:
            return f"{action_name}.create({target})"
        case operation_graph.OperationKind.DESTROY:
            return f"{action_name}.destroy({target})"
        case operation_graph.OperationKind.MOVE:
            if node.source is None:
                raise ValueError("a move node must have a source")
            return f"{action_name}.move({_short_chained_name(node.source)}, {target})"


def operation_graph_for(
    program_result: validation_result.ProgramValidationResult,
    action: str,
) -> operation_graph.OperationGraph:
    """Return the operation graph the reference-graph validator recorded for ``action``."""
    for typed_name, definition_result in program_result.definition_results.items():
        if typed_name.full_typed_name == action:
            graph = definition_result.operation_graph
            if graph is None:
                raise ValueError(f"no operation graph recorded for {action}")
            return graph
    raise KeyError(action)


def _disambiguated_labels(
    action_name: str, graph: operation_graph.OperationGraph
) -> list[str]:
    """Render each node's label, suffixing repeats of a shared label (``#2``, ``#3``)."""
    occurrences: collections.Counter[str] = collections.Counter()
    labels: list[str] = []
    for node in graph.nodes:
        base_label = _render_operation(action_name, node)
        occurrences[base_label] += 1
        count = occurrences[base_label]
        labels.append(base_label if count == 1 else f"{base_label}#{count}")
    return labels


def operation_dependencies(
    graph: operation_graph.OperationGraph,
    action: str,
) -> dict[str, list[str]]:
    """Map each of an action's operations to the operations it waits on.

    Operations are keyed in execution order and a root maps to an empty list.
    Where operations share a label, repeats are suffixed (``#2``, ``#3``) so that
    every operation remains a distinct key.
    """
    action_name = _action_display_name(action)
    labels = _disambiguated_labels(action_name, graph)
    return {
        labels[node.node_id]: [labels[dependency] for dependency in node.depends_on]
        for node in graph.nodes
    }


def get_results(
    source: str,
) -> dict[str, definition_postorder_validator.PostorderValidationResult]:
    """Validate source and return each definition's post-order result, keyed by full typed name."""
    results: dict[str, definition_postorder_validator.PostorderValidationResult] = {}
    action_analyze = definition_postorder_validator.ActionPostorderValidator.analyze

    def action_capture(
        self: definition_postorder_validator.ActionPostorderValidator,
    ) -> definition_postorder_validator.PostorderValidationResult:
        result = action_analyze(self)
        results[self._definition.typed_name.full_typed_name] = result  # pyright: ignore[reportPrivateUsage]
        return result

    with mock.patch.object(
        definition_postorder_validator.ActionPostorderValidator,
        "analyze",
        autospec=True,
        side_effect=action_capture,
    ):
        structural = program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
        assert_no_errors(structural)
        reference_graph_validator.ReferenceGraphValidator(
            structural.reference_graph,
            structural.definition_results,
        ).validate()
    return results


def get_contracts(
    source: str,
) -> dict[str, action_contract.ActionContract]:
    """Validate source and return each definition's contract, keyed by full typed name."""
    return {name: result.contract for name, result in get_results(source).items()}
