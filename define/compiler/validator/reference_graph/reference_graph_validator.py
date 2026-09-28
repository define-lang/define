"""Validation of the reference graph."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast, diagnostics
from define.compiler.graphs import (
    reference_graph_executor,
    reference_graph_order,
)
from define.compiler.validator import codegen_input, validation_result
from define.compiler.validator.reference_graph import (
    action_definition_validator,
    operation_definition_validator,
    position_occupancy,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict


def _requires_validation(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[ast.ActionDefinition | ast.OperationDefinition]:
    return isinstance(definition, ast.ActionDefinition | ast.OperationDefinition)


class ReferenceGraphValidationResult(msgspec.Struct, frozen=True):
    """What reference graph validation produces, beyond the diagnostics it reports."""

    codegen_input: codegen_input.CodegenInput


# TODO: We need a mode that forces a fake caller as the parent of any top-level
# action in this graph, to make sure that caller requirements are detected.
# (Otherwise developers can write bad action code and not realize it.)
class ReferenceGraphValidator:
    """Verifies definitions using the reference graph.

    This is the primary logical validator of Define. After completing structural
    validation, this step walks through the reference graph in DFS post-order
    and performs validations on each definition for logical correctness.
    """

    _definition_order: reference_graph_order.ReferenceGraphOrder
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _entry_action: ast.ActionDefinition | None
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _allow_entry_action_occupied_implied_position_requirements: bool

    def __init__(
        self,
        definition_order: reference_graph_order.ReferenceGraphOrder,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        *,
        entry_action: ast.ActionDefinition | None,
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ):
        """Initialize with the definition order and definition results.

        allow_entry_action_occupied_implied_position_requirements exists only
        for validation tests of behavior that requires such a program.
        """
        self._definition_order = definition_order
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
        definition_order = self._definition_order
        results = reference_graph_executor.process_selected_definitions(
            definition_order,
            _requires_validation,
            self._validate_definition,
            max_workers=max_workers,
        )

        actions: dict[str, codegen_input.ActionCodegenInput] = {}
        for result in results:
            if isinstance(result, validation_result.ActionPostorderValidationResult):
                definition = result.codegen_input.definition
                actions[definition.typed_name.full_typed_name] = result.codegen_input
        if (
            self._entry_action is not None
            and not self._allow_entry_action_occupied_implied_position_requirements
        ):
            self._validate_entry_action_requirements(self._entry_action)
        return ReferenceGraphValidationResult(
            codegen_input=codegen_input.CodegenInput(
                definition_order=definition_order,
                actions=actions,
            ),
        )

    def _validate_definition(
        self, definition: ast.ActionDefinition | ast.OperationDefinition
    ) -> validation_result.PostorderValidationResult:
        match definition:
            case ast.ActionDefinition():
                result = self._validate_action(definition)
            case ast.OperationDefinition():
                result = operation_definition_validator.OperationDefinitionValidator(
                    definition, self._definition_results
                ).analyze()
        definition_result = self._definition_results[definition.typed_name]
        for d in result.diagnostics:
            definition_result.add_diagnostic(d)
        return result

    def _validate_action(
        self, definition: ast.ActionDefinition
    ) -> validation_result.ActionPostorderValidationResult:
        definition_result = self._definition_results[definition.typed_name]
        result = action_definition_validator.ActionDefinitionValidator(
            definition=definition,
            particle_statement_validity=definition_result.particle_statement_validity,
            looked_at_position_validity=definition_result.looked_at_position_validity,
            definition_results=self._definition_results,
            validation_state=self._validation_state,
        ).analyze()
        self._validation_state.publish_contract(definition.typed_name, result.contract)
        return result

    def _validate_entry_action_requirements(
        self,
        entry_action: ast.ActionDefinition,
    ):
        definition_result = self._definition_results[entry_action.typed_name]
        contract = self._validation_state.get_contract(entry_action.typed_name)
        for requirement in contract.occupancy_requirements:
            if (
                requirement.position.starts_with_global
                and requirement.required_state
                == position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                definition_result.add_diagnostic(
                    diagnostics.EntryPointOccupiedImpliedPositionRequirementDiagnostic(
                        location=requirement.inferred_at,
                        position_name=requirement.position.source_chained_name,
                    )
                )
