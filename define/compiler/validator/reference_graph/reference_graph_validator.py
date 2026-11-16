"""Validation of the reference graph."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.association_resolution import (
    association_resolver,
)
from define.compiler.errors import diagnostics
from define.compiler.graphs import (
    reference_graph_executor,
)
from define.compiler.validator.reference_graph import (
    action_definition_validator,
    operation_definition_validator,
    position_occupancy,
    reference_graph_validation_state,
)

if typing.TYPE_CHECKING:
    from define.compiler.association_resolution import (
        concrete_program,
    )
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.graphs import (
        reference_graph_order,
    )
    from define.compiler.validator import validation_result


def _requires_validation(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[
    ast.ActionDefinition
    | ast.ValueOperationDefinition
    | ast.EncodingOperationDefinition
    | ast.LogicalOperationDefinition
    | ast.ValueDefinition
]:
    return isinstance(
        definition,
        ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.EncodingOperationDefinition
        | ast.LogicalOperationDefinition
        | ast.ValueDefinition,
    )


class ReferenceGraphValidationResult(msgspec.Struct, frozen=True):
    """What reference graph validation and association resolution produce, beyond the diagnostics they report."""

    concrete_program: concrete_program.ConcreteProgram


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
    _association_resolver: association_resolver.AssociationResolver
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
        self._association_resolver = association_resolver.AssociationResolver(
            definition_results
        )
        self._allow_entry_action_occupied_implied_position_requirements = (
            allow_entry_action_occupied_implied_position_requirements
        )

    def validate(
        self, max_workers: int | None = None
    ) -> ReferenceGraphValidationResult:
        """Validate every definition in direct-reference-first order, resolving each to concrete code once it is validated."""
        definition_order = self._definition_order
        _ = reference_graph_executor.process_definitions(
            definition_order,
            _requires_validation,
            self._validate_definition,
            max_workers=max_workers,
        )
        entry_action = self._entry_action
        if (
            entry_action is not None
            and not self._allow_entry_action_occupied_implied_position_requirements
        ):
            self._validate_entry_action_requirements(entry_action)
        return ReferenceGraphValidationResult(
            concrete_program=self._association_resolver.concrete_program(
                definition_order
            )
        )

    def _validate_definition(
        self,
        definition: ast.ActionDefinition
        | ast.ValueOperationDefinition
        | ast.EncodingOperationDefinition
        | ast.LogicalOperationDefinition
        | ast.ValueDefinition,
    ):
        """Validate a definition, then resolve it to concrete code."""
        definition_diagnostics = self._definition_results[
            definition.typed_name
        ].diagnostics
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
                        definition, self._definition_results
                    ).analyze()
                )
                definition_diagnostics.extend(value_operation_result.diagnostics)
                if value_operation_result.steps is not None:
                    definition_diagnostics.extend(
                        resolver.resolve_value_operation(
                            definition, value_operation_result.steps
                        )
                    )
            case ast.EncodingOperationDefinition():
                definition_diagnostics.extend(
                    resolver.resolve_encoding_operation(definition)
                )
            case ast.LogicalOperationDefinition():
                definition_diagnostics.extend(
                    resolver.resolve_logical_operation(definition)
                )
            case ast.ValueDefinition():
                definition_diagnostics.extend(resolver.resolve_value(definition))

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
                definition_result.diagnostics.append(
                    diagnostics.EntryPointOccupiedImpliedPositionRequirementDiagnostic(
                        location=requirement.inferred_at,
                        position_name=requirement.position.source_chained_name,
                    )
                )
