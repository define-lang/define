"""Validation of the reference graph."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler import ast, diagnostics
from define.compiler.graphs import (
    action_call_graph,
    reference_graph,
    reference_graph_executor,
)
from define.compiler.validator.reference_graph import (
    action_contract,
    definition_postorder_validator,
    operation_graph,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result

# Position definitions get no validation and so produce None.
type _PostorderResult = definition_postorder_validator.PostorderValidationResult | None


@dataclass(frozen=True, slots=True)
class ReferenceGraphValidationResult:
    """What reference graph validation produces, beyond the diagnostics it reports."""

    definition_order: reference_graph_executor.ReferenceGraphOrder
    action_call_graph: action_call_graph.ActionCallGraph
    # The DLP 44 operation dependency graph of every action.
    operation_graphs: operation_graph.OperationGraphs


# TODO: We need a mode that forces a fake caller as the parent of any top-level
# action in this graph, to make sure that caller requirements are detected.
# (Otherwise developers can write bad action code and not realize it.)
class ReferenceGraphValidator:
    """Verifies definitions using the reference graph.

    This is the primary logical validator of Define. After completing structural
    validation, this step walks through the reference graph in DFS post-order
    and performs validations on each definition for logical correctness.
    """

    _reference_graph: reference_graph.ReferenceGraph
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, validation_result.DefinitionValidationResult
    ]
    _entry_action: ast.ActionDefinition | None
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _allow_entry_action_occupied_implied_position_requirements: bool

    def __init__(
        self,
        graph: reference_graph.ReferenceGraph,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, validation_result.DefinitionValidationResult
        ],
        *,
        entry_action: ast.ActionDefinition | None,
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ):
        """Initialize with the reference graph and definition results.

        allow_entry_action_occupied_implied_position_requirements exists only
        for validation tests of behavior that requires such a program.
        """
        self._reference_graph = graph
        self._definition_results = definition_results
        self._entry_action = entry_action
        self._validation_state = (
            reference_graph_validation_state.ReferenceGraphValidationState()
        )
        self._allow_entry_action_occupied_implied_position_requirements = (
            allow_entry_action_occupied_implied_position_requirements
        )

    def validate(
        self, max_workers: int | None = None
    ) -> ReferenceGraphValidationResult:
        """Validate every definition in direct-reference-first order."""
        definition_order = reference_graph_executor.ReferenceGraphOrder(
            self._reference_graph
        )
        results = reference_graph_executor.process_definitions(
            definition_order,
            self._validate_definition,
            max_workers=max_workers,
        )

        call_graph = action_call_graph.ActionCallGraph()
        operation_graphs = operation_graph.OperationGraphs()
        for definition, result in zip(
            definition_order.definitions, results, strict=True
        ):
            if result is None:
                continue
            definition_result = self._definition_results[definition.typed_name]
            for d in result.diagnostics:
                definition_result.add_diagnostic(d)
            for edge in result.edges:
                call_graph.add_edge(edge.source, edge.target)
            operation_graphs[definition.typed_name] = result.operation_graph
        if (
            self._entry_action is not None
            and not self._allow_entry_action_occupied_implied_position_requirements
        ):
            self._validate_entry_action_requirements(self._entry_action)
        return ReferenceGraphValidationResult(
            definition_order=definition_order,
            action_call_graph=call_graph,
            operation_graphs=operation_graphs,
        )

    def _validate_definition(
        self, definition: ast.QualityDefinition
    ) -> _PostorderResult:
        if not isinstance(definition, ast.ActionDefinition):
            return None
        return self._validate_action(definition)

    def _validate_action(
        self, definition: ast.ActionDefinition
    ) -> definition_postorder_validator.PostorderValidationResult:
        definition_result = self._definition_results[definition.typed_name]
        result = definition_postorder_validator.ActionPostorderValidator(
            definition_result,
            self._definition_results,
            self._validation_state,
        ).analyze()
        self._validation_state.publish_contract(definition.typed_name, result.contract)
        return result

    def _validate_entry_action_requirements(
        self,
        entry_action: ast.ActionDefinition,
    ):
        definition_result = self._definition_results[entry_action.typed_name]
        contract = self._validation_state.get_contract(entry_action.typed_name)
        for requirement in contract.requirements.values():
            if (
                requirement.position.starts_with_global
                and requirement.required_state
                == action_contract.PositionOccupancyState.OCCUPIED
            ):
                definition_result.add_diagnostic(
                    diagnostics.EntryPointOccupiedImpliedPositionRequirementDiagnostic(
                        location=requirement.inferred_at,
                        position_name=requirement.position.source_chained_name,
                    )
                )
