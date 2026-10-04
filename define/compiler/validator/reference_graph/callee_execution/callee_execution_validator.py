"""Trigger a callee of the action being validated, checking its requirements against the action's state."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import chained_name
    from define.compiler.validator import scope_tracker
    from define.compiler.validator.reference_graph import (
        action_contract,
        action_requirement_validator,
    )
    from define.compiler.validator.reference_graph.callee_execution import (
        callee_execution,
    )
    from define.compiler.validator.reference_graph.dead_code import (
        dead_constraint_validator,
        dead_value_write_validator,
    )
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract_validator,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class CalleeExecutionValidationResult(msgspec.Struct):
    """What validating one callee execution produces."""

    codegen_execution: codegen_input.ActionExecution
    # Destruction Contracts this action takes on from the callee.
    destruction_contracts: list[action_contract.DestructionContracts]
    diagnostics: list[diagnostics.Diagnostic]


@typing.final
class CalleeExecutionValidator:
    """Triggers callees of the action being validated, checking their requirements against its state."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        tracker: particle_tracker.ParticleTracker,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
        dead_constraint_validator: dead_constraint_validator.DeadConstraintValidator,
        dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator,
        destruction_contract_validator: destruction_contract_validator.DestructionContractValidator,
    ):
        """Validate callees of ``definition`` against the state ``tracker`` holds."""
        self._definition = definition
        self._tracker = tracker
        self._requirement_validator = requirement_validator
        self._dead_constraint_validator = dead_constraint_validator
        self._dead_value_write_validator = dead_value_write_validator
        self._destruction_contract_validator = destruction_contract_validator

    def validate(
        self,
        execution: callee_execution.CalleeExecution,
        scope: scope_tracker.ScopeTracker,
    ) -> CalleeExecutionValidationResult:
        """Trigger the callee, and return what validating its execution produces."""
        action_chain = execution.action_chain
        contract = execution.contract
        action_assignment = execution.action_assignment
        # Requirement propagation and requirement checking each need every
        # requirement's position from the caller's perspective
        # (req.position.in_caller(action_chain)). Deriving it is a fresh
        # allocation, so compute it once here and hand the same objects to both
        # rather than rebuilding it twice per requirement per trigger.
        requirements_in_caller = contract.occupancy_requirements_in_caller(action_chain)
        self._dead_constraint_validator.mark_callee_contract_constraints_alive(
            requirements_in_caller, scope
        )
        self._requirement_validator.propagate_action_requirements(
            action_chain,
            scope,
            requirements_in_caller,
            action_assignment,
        )
        validation_diagnostics = (
            self._requirement_validator.check_occupancy_requirements(
                execution, requirements_in_caller
            )
        )
        value_requirements = contract.value_requirements_in_caller(action_chain)
        self._requirement_validator.propagate_value_requirements(
            action_chain, value_requirements, action_assignment
        )
        self._dead_value_write_validator.mark_required_values_used(value_requirements)
        validation_diagnostics.extend(
            self._requirement_validator.check_value_requirements(
                execution, value_requirements
            )
        )
        destruction_result = self._destruction_contract_validator.validate(
            contract.destruction_contracts,
            action_chain,
        )
        validation_diagnostics.extend(destruction_result.diagnostics)
        codegen_execution = codegen_input.ActionExecution(action=action_chain)
        codegen_execution.destruction_connections.extend(destruction_result.connections)
        occupied_interface_child_position_violations = self._tracker.trigger_action(
            action_chain,
            contract,
            parent_particle=execution.parent_particle,
        )
        validation_diagnostics.extend(
            self._record_occupied_interface_child_position_violations(
                execution, occupied_interface_child_position_violations
            )
        )
        return CalleeExecutionValidationResult(
            codegen_execution=codegen_execution,
            destruction_contracts=destruction_result.propagated_contracts,
            diagnostics=validation_diagnostics,
        )

    def _record_occupied_interface_child_position_violations(
        self,
        execution: callee_execution.CalleeExecution,
        occupied_interface_child_position_violations: Sequence[
            tuple[chained_name.PositionReferenceTuple, ast.SourceLocation]
        ],
    ) -> list[diagnostics.Diagnostic]:
        """Mark occupied interface child positions found when one callee triggers as in error, and return a diagnostic for each."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        enclosing_fqun = self._definition.typed_name.name_content.fqun
        for position, arrived_at in occupied_interface_child_position_violations:
            # The callee ran with a particle where it expected none, so what
            # is there now cannot be trusted.
            self._tracker.mark_error_by_key(position)
            validation_diagnostics.append(
                diagnostics.OccupiedActionInterfaceWhenActionTriggersDiagnostic(
                    location=execution.diagnostic_location,
                    arrived_at=arrived_at,
                    action_name=execution.action_chain.get_last_action().source_typed_name,
                    position_name=ast.source_form_chained_name(
                        position, enclosing_fqun.canonical
                    ),
                )
            )
        return validation_diagnostics
