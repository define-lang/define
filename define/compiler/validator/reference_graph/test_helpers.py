"""Readable representations of validator-recorded action triggers for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from define.compiler.validator.reference_graph import (
        destruction_contract,
        reference_graph_validator,
    )


def action_graph(
    result: reference_graph_validator.ReferenceGraphValidationResult,
) -> list[tuple[str, str]]:
    """List triggered actions in definition postorder and statement order.

    Contract contributions precede the execution where they are verified.
    Repeated triggers produce repeated edges. Use action_graph_set only for
    reference-graph diamonds that make the order nondeterministic.
    """
    edges: list[tuple[str, str]] = []
    for definition in result.codegen_input.definition_order.definitions:
        if not isinstance(definition, ast.ActionDefinition):
            continue
        edges.extend(_definition_edges(result, definition))
    return edges


def _definition_edges(
    result: reference_graph_validator.ReferenceGraphValidationResult,
    definition: ast.ActionDefinition,
) -> Iterator[tuple[str, str]]:
    source = definition.typed_name.source_typed_name
    for step in result.codegen_input.actions[
        definition.typed_name.full_typed_name
    ].steps:
        if isinstance(step, codegen_input.ActionExecution):
            yield from _destruction_contract_edges(step.destruction_connections)
            yield source, step.action.get_last_action().full_typed_name
        elif isinstance(step, codegen_input.Destruction):
            for destructor in step.destructors:
                yield source, destructor.get_last_action().full_typed_name


def _destruction_contract_edges(
    connections: Iterable[destruction_contract.DestructionConnection],
) -> Iterator[tuple[str, str]]:
    for connection in connections:
        contribution = connection.contribution
        if contribution is None:
            continue
        destroyer = contribution.destruction_fact.destruction.destroying_action
        for destructor in contribution.destructors:
            yield (
                destroyer.source_typed_name,
                destructor.get_last_action().full_typed_name,
            )


def action_graph_set(
    result: reference_graph_validator.ReferenceGraphValidationResult,
) -> set[tuple[str, str]]:
    """Return trigger edges for reference-graph diamonds with nondeterministic order."""
    return set(action_graph(result))
