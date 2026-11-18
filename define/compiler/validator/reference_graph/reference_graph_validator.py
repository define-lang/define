"""Validation of the reference graph."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.graphs import (
    reference_graph_executor,
)
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import (
    action_definition_validator,
    operation_definition_validator,
    position_occupancy,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.association_resolution import association_resolver
    from define.compiler.graphs import (
        reference_graph_order,
    )


def _requires_validation(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[
    ast.ActionDefinition
    | ast.ValueOperationDefinition
    | ast.LogicalOperationDefinition
    | ast.ValueDefinition
]:
    # Association resolution validates Encoding Operations once it has the
    # ones it chooses loaded.
    return isinstance(
        definition,
        ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.LogicalOperationDefinition
        | ast.ValueDefinition,
    )


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
    _definitions: Mapping[str, ast.GlobalDefinition]
    _structural_results: Mapping[str, validation_result.DefinitionValidationResult]
    _entry_action: ast.ActionDefinition | None
    _validation_state: reference_graph_validation_state.ReferenceGraphValidationState
    _association_resolver: association_resolver.AssociationResolver
    _allow_entry_action_occupied_implied_position_requirements: bool

    def __init__(
        self,
        definition_order: reference_graph_order.ReferenceGraphOrder,
        definitions: Mapping[str, ast.GlobalDefinition],
        structural_results: Mapping[str, validation_result.DefinitionValidationResult],
        resolver: association_resolver.AssociationResolver,
        *,
        entry_action: ast.ActionDefinition | None,
        allow_entry_action_occupied_implied_position_requirements: bool = False,
    ):
        """Initialize with the definition order, the program's definitions by full typed name, the structural result of each definition by full typed name, and the association resolver that resolves each definition once it is validated.

        allow_entry_action_occupied_implied_position_requirements exists only
        for validation tests of behavior that requires such a program.
        """
        self._definition_order = definition_order
        self._definitions = definitions
        self._structural_results = structural_results
        self._entry_action = entry_action
        self._validation_state = (
            reference_graph_validation_state.ReferenceGraphValidationState()
        )
        self._association_resolver = resolver
        self._allow_entry_action_occupied_implied_position_requirements = (
            allow_entry_action_occupied_implied_position_requirements
        )

    def validate(
        self, max_workers: int | None = None
    ) -> list[validation_result.DefinitionDiagnostics]:
        """Validate every definition in direct-reference-first order, resolving each to concrete code once it is validated, and return the diagnostics about each definition that has any."""
        found: list[validation_result.DefinitionDiagnostics] = []
        for definition_diagnostics in reference_graph_executor.process_definitions(
            self._definition_order,
            _requires_validation,
            self._validate_definition,
            max_workers=max_workers,
        ):
            if definition_diagnostics.diagnostics:
                found.append(definition_diagnostics)
        entry_action = self._entry_action
        if (
            entry_action is not None
            and not self._allow_entry_action_occupied_implied_position_requirements
        ):
            entry_action_diagnostics = self._entry_action_requirement_diagnostics(
                entry_action
            )
            if entry_action_diagnostics:
                found.append(
                    validation_result.DefinitionDiagnostics(
                        definition=entry_action, diagnostics=entry_action_diagnostics
                    )
                )
        return found

    def _validate_definition(
        self,
        definition: ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.LogicalOperationDefinition
        | ast.ValueDefinition,
    ) -> validation_result.DefinitionDiagnostics:
        """Validate a definition, then resolve it to concrete code, and return the diagnostics about it."""
        definition_diagnostics: list[diagnostics.Diagnostic] = []
        resolver = self._association_resolver
        match definition:
            case ast.ActionDefinition():
                action_result = self._validate_action(definition)
                definition_diagnostics.extend(action_result.diagnostics)
                definition_diagnostics.extend(
                    resolver.resolve_action(action_result.action)
                )
            case ast.ValueOperationDefinition():
                value_operation_result = (
                    operation_definition_validator.ValueOperationDefinitionValidator(
                        definition,
                        self._definitions,
                        structurally_valid=not self._structural_results[
                            definition.typed_name.full_typed_name
                        ].diagnostics,
                    ).analyze()
                )
                definition_diagnostics.extend(value_operation_result.diagnostics)
                if value_operation_result.steps is not None:
                    definition_diagnostics.extend(
                        resolver.resolve_value_operation(
                            definition, value_operation_result.steps
                        )
                    )
            case ast.LogicalOperationDefinition():
                definition_diagnostics.extend(
                    resolver.resolve_logical_operation(definition)
                )
            case ast.ValueDefinition():
                definition_diagnostics.extend(resolver.resolve_value(definition))
        return validation_result.DefinitionDiagnostics(
            definition=definition, diagnostics=definition_diagnostics
        )

    def _validate_action(
        self, definition: ast.ActionDefinition
    ) -> validation_result.ActionPostorderValidationResult:
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
        self,
        entry_action: ast.ActionDefinition,
    ) -> list[diagnostics.Diagnostic]:
        requirement_diagnostics: list[diagnostics.Diagnostic] = []
        contract = self._validation_state.get_contract(entry_action.typed_name)
        for requirement in contract.occupancy_requirements:
            if (
                requirement.position.starts_with_global
                and requirement.required_state
                == position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                requirement_diagnostics.append(
                    diagnostics.EntryPointOccupiedImpliedPositionRequirementDiagnostic(
                        location=requirement.inferred_at,
                        position_name=requirement.position.source_chained_name,
                    )
                )
        return requirement_diagnostics
