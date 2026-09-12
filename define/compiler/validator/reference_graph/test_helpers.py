"""Readable representations of validator-recorded action triggers for tests."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler.validator.reference_graph import reference_graph_validator


def action_graph(
    result: reference_graph_validator.ReferenceGraphValidationResult,
) -> list[tuple[str, str]]:
    """List triggered actions in definition postorder and statement order.

    Repeated triggers produce repeated edges. Use action_graph_set only for
    reference-graph diamonds that make the order nondeterministic.
    """
    edges: list[tuple[str, str]] = []
    for definition in result.definition_order.definitions:
        if not isinstance(definition, ast.ActionDefinition):
            continue
        source = definition.typed_name.source_typed_name
        block = definition.action_statements
        for statement in itertools.chain(block.statements, (block,)):
            for action in result.triggered_actions.get(statement.location, ()):
                edges.append((source, action.get_last_action().full_typed_name))
    return edges


def action_graph_set(
    result: reference_graph_validator.ReferenceGraphValidationResult,
) -> set[tuple[str, str]]:
    """Return trigger edges for reference-graph diamonds with nondeterministic order."""
    return set(action_graph(result))
