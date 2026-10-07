"""Trigger a callee of the action being validated, checking its requirements against the action's state."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph.callee_execution import (
    callee_execution,
)
from define.compiler.validator.reference_graph.destruction import (
    destruction_contract_validator,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import chained_name
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        action_contract,
        action_requirement_validator,
        reference_graph_validation_state,
    )
    from define.compiler.validator.reference_graph.dead_code import (
        dead_constraint_validator,
        dead_value_write_validator,
    )
    from define.compiler.validator.reference_graph.destruction import (
        destruction_contract,
    )
    from define.compiler.validator.reference_graph.particles import (
        particle_tracker,
    )


class CalleeExecutionValidationResult(msgspec.Struct):
    """What validating one callee execution produces."""

    destruction_connections: list[destruction_contract.DestructionConnection]
    # Destruction Contracts this action takes on from the callee.
    destruction_contracts: list[action_contract.DestructionContracts]
    diagnostics: list[diagnostics.Diagnostic]


@typing.final
class CalleeExecutionValidator:
    """Triggers callees of the action being validated, checking their requirements against its state."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        tracker: particle_tracker.ParticleTracker,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
        dead_constraint_validator: dead_constraint_validator.DeadConstraintValidator,
        dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator,
    ):
        """Validate callees of ``definition`` against the state ``tracker`` holds."""
        self._definition = definition
        self._tracker = tracker
        self._requirement_validator = requirement_validator
        self._dead_constraint_validator = dead_constraint_validator
        self._dead_value_write_validator = dead_value_write_validator
        self._destruction_contract_validator = (
            destruction_contract_validator.DestructionContractValidator(
                definition, definition_results, validation_state, tracker
            )
        )

    def validate(
        self,
        execution: callee_execution.CalleeExecution,
        scope: scope_tracker.ScopeTracker,
    ) -> CalleeExecutionValidationResult:
        """Trigger the callee, and return what validating its execution produces.

        This records what triggering the callee requires of this action's
        state, but does not apply the callee's Guarantees; the caller applies
        them when it needs them.
        """
        action_chain = execution.action_chain
        contract = execution.contract
        action_assignment = execution.action_assignment
        # Requirement propagation and requirement checking each need every
        # requirement's position from the caller's perspective
        # (req.position.in_caller(action_chain)). Deriving it is a fresh
        # allocation, so compute it once here and hand the same objects to both
        # rather than rebuilding it twice per requirement per trigger.
        requirements_in_caller = contract.occupancy_requirements_in_caller(
            action_chain, action_assignment
        )
        self._dead_constraint_validator.mark_callee_contract_constraints_alive(
            requirements_in_caller, scope
        )
        self._requirement_validator.propagate_action_requirements(
            action_chain.location, requirements_in_caller, scope
        )
        validation_diagnostics = (
            self._requirement_validator.check_occupancy_requirements(
                execution, requirements_in_caller
            )
        )
        value_requirements = contract.value_requirements_in_caller(
            action_chain, action_assignment
        )
        self._requirement_validator.propagate_value_requirements(
            action_chain.location, value_requirements
        )
        self._dead_value_write_validator.mark_required_values_used(value_requirements)
        validation_diagnostics.extend(
            self._requirement_validator.check_value_requirements(
                execution, value_requirements
            )
        )
        destruction_result = self._destruction_contract_validator.validate(
            contract.destruction_contracts, action_chain
        )
        # Validating a Destructor can record a requirement that makes this
        # action assume a particle is in a position. A walk that ran after
        # that would find the assumed particle and treat it as destroyed, so
        # the Destructors are validated only after every walk is done.
        for destructor_execution in destruction_result.destructor_executions:
            validation_diagnostics.extend(
                self._validate_destructor_in_callee(destructor_execution, scope)
            )
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
            destruction_connections=destruction_result.connections,
            destruction_contracts=destruction_result.propagated_contracts,
            diagnostics=validation_diagnostics,
        )

    def _validate_destructor_in_callee(
        self,
        execution: callee_execution.DestructorInCalleeExecution,
        scope: scope_tracker.ScopeTracker,
    ) -> list[diagnostics.Diagnostic]:
        """Validate a Destructor that ran when the callee destroyed its particle, as though it were running at the moment of destruction."""
        validation_diagnostics = self._validate_destructor_occupancy_requirements(
            execution, scope
        )
        validation_diagnostics.extend(
            self._validate_destructor_value_requirements(execution)
        )
        return validation_diagnostics

    def _validate_destructor_occupancy_requirements(
        self,
        execution: callee_execution.DestructorInCalleeExecution,
        scope: scope_tracker.ScopeTracker,
    ) -> list[diagnostics.Diagnostic]:
        """Validate the occupancy requirements of a Destructor that ran when the callee destroyed its particle."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        # What the callee and the actions below it recorded decides a
        # requirement. Anything else is as it was when this action triggered
        # the callee, so it is an ordinary requirement at the position it
        # was in then.
        to_check: list[action_contract.OccupancyRequirementInCaller] = []
        to_propagate: list[action_contract.OccupancyRequirementInCaller] = []
        for occupancy_requirement in execution.contract.occupancy_requirements:
            at_destruction = execution.occupancy_at_destruction(occupancy_requirement)
            if isinstance(at_destruction, callee_execution.KnownAtDestruction):
                if occupancy_requirement.is_violated_by(at_destruction.occupancy):
                    validation_diagnostics.append(
                        execution.destruction_requirement_violation(
                            occupancy_requirement,
                            at_destruction.position,
                            self._definition,
                        )
                    )
                continue
            to_check.append(
                execution.requirement_in_caller(occupancy_requirement, at_destruction)
            )
            to_propagate.append(
                execution.callee_requirement_in_caller(
                    occupancy_requirement, at_destruction
                )
            )
        self._requirement_validator.propagate_action_requirements(
            execution.state_at_destruction.trigger.callee.location, to_propagate, scope
        )
        validation_diagnostics.extend(
            self._requirement_validator.check_occupancy_requirements(
                execution, to_check
            )
        )
        return validation_diagnostics

    def _validate_destructor_value_requirements(
        self, execution: callee_execution.DestructorInCalleeExecution
    ) -> list[diagnostics.Diagnostic]:
        """Validate the value requirements of a Destructor that ran when the callee destroyed its particle."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        # What the callee and the actions below it recorded decides a
        # requirement. Anything else is as it was when this action triggered
        # the callee, so it is an ordinary requirement at the position it
        # was in then.
        to_check: list[action_contract.ValueRequirementInCaller] = []
        to_propagate: list[action_contract.ValueRequirementInCaller] = []
        for value_requirement in execution.contract.value_requirements:
            at_destruction = execution.value_at_destruction(value_requirement)
            if isinstance(at_destruction, callee_execution.KnownAtDestruction):
                particle = execution.state_at_destruction.caller_particle_at(
                    at_destruction.position_in_child_state
                )
                if particle is not None:
                    self._dead_value_write_validator.mark_particle_used(particle)
                if value_requirement.is_violated_by(
                    at_destruction.occupancy, at_destruction.value_state
                ):
                    validation_diagnostics.append(
                        execution.destruction_requirement_violation(
                            value_requirement,
                            at_destruction.position,
                            self._definition,
                        )
                    )
                continue
            to_check.append(
                execution.requirement_in_caller(value_requirement, at_destruction)
            )
            to_propagate.append(
                execution.callee_requirement_in_caller(
                    value_requirement, at_destruction
                )
            )
        self._requirement_validator.propagate_value_requirements(
            execution.state_at_destruction.trigger.callee.location, to_propagate
        )
        self._dead_value_write_validator.mark_required_values_used(to_propagate)
        validation_diagnostics.extend(
            self._requirement_validator.check_value_requirements(execution, to_check)
        )
        return validation_diagnostics

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
