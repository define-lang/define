"""Validation of the reference graph."""

from __future__ import annotations

import typing

from define.compiler.graphs import action_call_graph, reference_graph
from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
)

if typing.TYPE_CHECKING:
    from define.compiler.validator import validation_result


# TODO: We need a mode that forces a fake position init block as the parent
# caller of any top-level action in this graph, to make sure that caller
# requirements are detected. (Otherwise developers can write bad action
# code and not realize it.)
class ReferenceGraphValidator:
    """Verifies all definitions using the reference graph.

    This is the primary logical validator of Define. After completing structural
    validation, this step walks through the reference graph in DFS post-order
    and performs validations on each definition for logical correctness.
    """

    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: dict[str, validation_result.DefinitionValidationResult]
    _action_contracts: dict[str, action_contract.ActionContract]
    _position_contracts: dict[str, action_contract.PositionInitBlockContract]

    def __init__(
        self,
        graph: reference_graph.ReferenceGraph,
        definition_results: dict[str, validation_result.DefinitionValidationResult],
    ):
        """Initialize with the reference graph and definition results."""
        self._reference_graph = graph
        self._definition_results = definition_results
        self._action_contracts = {}
        self._position_contracts = {}

    def validate(self) -> action_call_graph.ActionCallGraph:
        """Run analysis for all definitions in a depth-first-search, post-order."""
        call_graph = action_call_graph.ActionCallGraph()
        # We use dfs_postorder_all rather than dfs_postorder_from because the
        # reference graph can contain multiple roots (any action or position
        # that is not referenced by anything else creates a new graph).
        for definition in self._reference_graph.dfs_postorder_all():
            name = definition.typed_name.source_typed_name
            definition_result = self._definition_results[name]
            analyzer = definition_postorder_validator.create_postorder_validator(
                definition_result,
                self._definition_results,
                self._action_contracts,
                self._position_contracts,
            )
            result = analyzer.analyze()
            for d in result.diagnostics:
                definition_result.add_diagnostic(d)
            for edge in result.edges:
                call_graph.add_edge(edge.source, edge.target)
            if isinstance(result.contract, action_contract.ActionContract):
                self._action_contracts[name] = result.contract
            elif isinstance(result.contract, action_contract.PositionInitBlockContract):
                self._position_contracts[name] = result.contract
        return call_graph
