"""Validation of the reference graph."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.data_structures import typed_name_dict
from define.compiler.graphs import action_call_graph, reference_graph
from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
)

if typing.TYPE_CHECKING:
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import operation_graph


@dataclass(frozen=True, slots=True)
class ReferenceGraphValidationResult:
    """What reference graph validation produces, beyond the diagnostics it reports."""

    action_call_graph: action_call_graph.ActionCallGraph
    # The DLP 44 operation dependency graph of every action.
    operation_graphs: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, operation_graph.OperationGraph
    ]


# TODO: We need a mode that forces a fake caller as the parent of any top-level
# action in this graph, to make sure that caller requirements are detected.
# (Otherwise developers can write bad action code and not realize it.)
class ReferenceGraphValidator:
    """Verifies all definitions using the reference graph.

    This is the primary logical validator of Define. After completing structural
    validation, this step walks through the reference graph in DFS post-order
    and performs validations on each definition for logical correctness.
    """

    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _action_contracts: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, action_contract.ActionContract
    ]
    _definition_quality_cache: dict[
        tuple[str, ...], tuple[ast.GlobalTypedNameReference, ...]
    ]

    def __init__(
        self,
        graph: reference_graph.ReferenceGraph,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
    ):
        """Initialize with the reference graph and definition results."""
        self._reference_graph = graph
        self._definition_results = definition_results
        self._action_contracts = typed_name_dict.TypedNameDict()
        self._definition_quality_cache = {}

    def validate(self) -> ReferenceGraphValidationResult:
        """Run analysis for all definitions in a depth-first-search, post-order."""
        call_graph = action_call_graph.ActionCallGraph()
        operation_graphs: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, operation_graph.OperationGraph
        ] = typed_name_dict.TypedNameDict()
        # We use dfs_postorder_all rather than dfs_postorder_from because the
        # reference graph can contain multiple roots (any action or position
        # that is not referenced by anything else creates a new graph).
        for definition in self._reference_graph.dfs_postorder_all():
            definition_result = self._definition_results[definition.typed_name]
            # Only actions need post-order validation; positions contribute nothing.
            if not isinstance(definition_result.definition, ast.ActionDefinition):
                continue
            result = definition_postorder_validator.ActionPostorderValidator(
                definition_result,
                self._definition_results,
                self._action_contracts,
                self._definition_quality_cache,
            ).analyze()
            for d in result.diagnostics:
                definition_result.add_diagnostic(d)
            for edge in result.edges:
                call_graph.add_edge(edge.source, edge.target)
            self._action_contracts[definition.typed_name] = result.contract
            operation_graphs[definition.typed_name] = result.operation_graph
        return ReferenceGraphValidationResult(
            action_call_graph=call_graph,
            operation_graphs=operation_graphs,
        )
