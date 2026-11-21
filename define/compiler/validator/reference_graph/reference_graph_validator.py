"""Validation of the reference graph."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.errors import reference_graph_diagnostics
from define.compiler.validator.reference_graph import (
    abstract_program,
    action_definition_validator,
    operation_definition_validator,
    position_occupancy,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.errors import diagnostics
    from define.compiler.validator.reference_graph import (
        action_contract,
    )
    from define.compiler.validator.structural import structural_result


class DefinitionValidation(msgspec.Struct, frozen=True):
    """What validating one definition found: its diagnostics, and what association resolution resolves, if anything."""

    diagnostics: list[diagnostics.Diagnostic]
    # None for a Value Operation whose steps validation could not work out,
    # which nothing can resolve.
    abstract: abstract_program.AbstractDefinition | None


def requires_validation(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[
    ast.ActionDefinition | ast.ValueOperationDefinition | ast.LogicalOperationDefinition
]:
    """Whether reference graph validation validates a definition, which association resolution then resolves."""
    # Association resolution validates Encoding Operations once it has the
    # ones it chooses loaded.
    return isinstance(
        definition,
        ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.LogicalOperationDefinition,
    )


# TODO: We need a mode that forces a fake caller as the parent of any top-level
# action in this graph, to make sure that caller requirements are detected.
# (Otherwise developers can write bad action code and not realize it.)
class ReferenceGraphValidator:
    """Verifies definitions using the reference graph.

    This is the primary logical validator of Define. After structural
    validation, it validates each definition for logical correctness. A
    definition must be validated only once everything it directly references
    is, because validating an action reads the contracts of the actions it
    triggers.
    """

    _definitions: Mapping[str, ast.GlobalDefinition]
    _structural_results: Mapping[str, structural_result.StructuralDefinitionResult]
    _entry_action: ast.ActionDefinition | None
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _allow_entry_action_occupied_implied_position_requirements: bool

    def __init__(
        self,
        definitions: Mapping[str, ast.GlobalDefinition],
        structural_results: Mapping[str, structural_result.StructuralDefinitionResult],
        *,
        entry_action: ast.ActionDefinition | None,
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ):
        """Initialize with the program's definitions by full typed name, and the structural result of each definition by full typed name.

        allow_entry_action_occupied_implied_position_requirements exists only
        for validation tests of behavior that requires such a program.
        """
        self._definitions = definitions
        self._structural_results = structural_results
        self._entry_action = entry_action
        self._validation_state = (
            reference_graph_validation_state.ReferenceGraphValidationState()
        )
        self._allow_entry_action_occupied_implied_position_requirements = (
            allow_entry_action_occupied_implied_position_requirements
        )

    def validate_definition(
        self,
        definition: ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.LogicalOperationDefinition,
    ) -> DefinitionValidation:
        """Validate a definition, and return what validation found.

        Safe to call on any worker thread.
        """
        match definition:
            case ast.ActionDefinition():
                action_result = self._validate_action(definition)
                definition_diagnostics = action_result.diagnostics
                if definition is self._entry_action:
                    definition_diagnostics.extend(
                        self._entry_action_requirement_diagnostics(
                            action_result.contract
                        )
                    )
                return DefinitionValidation(
                    diagnostics=definition_diagnostics,
                    abstract=action_result.action,
                )
            case ast.ValueOperationDefinition():
                value_operation_result = (
                    operation_definition_validator.ValueOperationDefinitionValidator(
                        definition,
                        self._definitions,
                        structurally_valid=self._structural_results[
                            definition.typed_name.full_typed_name
                        ].structurally_valid,
                    ).analyze()
                )
                steps = value_operation_result.steps
                return DefinitionValidation(
                    diagnostics=value_operation_result.diagnostics,
                    abstract=None
                    if steps is None
                    else abstract_program.AbstractValueOperation(
                        definition=definition, steps=steps
                    ),
                )
            case ast.LogicalOperationDefinition():
                return DefinitionValidation(diagnostics=[], abstract=definition)

    def _validate_action(
        self, definition: ast.ActionDefinition
    ) -> action_definition_validator.ActionValidatorResult:
        definition_result = self._structural_results[
            definition.typed_name.full_typed_name
        ]
        result = action_definition_validator.ActionDefinitionValidator(
            definition=definition,
            particle_statement_validity=definition_result.particle_statement_validity,
            looked_at_position_validity=definition_result.looked_at_position_validity,
            definitions=self._definitions,
            validation_state=self._validation_state,
        ).analyze()
        self._validation_state.publish_contract(definition.typed_name, result.contract)
        return result

    def _entry_action_requirement_diagnostics(
        self, contract: action_contract.ActionContract
    ) -> list[diagnostics.Diagnostic]:
        if self._allow_entry_action_occupied_implied_position_requirements:
            return []
        requirement_diagnostics: list[diagnostics.Diagnostic] = []
        for requirement in contract.occupancy_requirements:
            if (
                requirement.position.starts_with_global
                and requirement.required_state
                == position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                requirement_diagnostics.append(
                    reference_graph_diagnostics.EntryPointOccupiedImpliedPositionRequirementDiagnostic(
                        location=requirement.inferred_at,
                        position_name=requirement.position.source_chained_name,
                    )
                )
        return requirement_diagnostics
