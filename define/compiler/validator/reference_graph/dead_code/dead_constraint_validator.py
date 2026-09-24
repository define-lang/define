"""Validate dead constraints and untriggered Actions."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics
from define.compiler.validator.reference_graph import position_occupancy
from define.compiler.validator.reference_graph.dead_code import dead_constraint_tracker

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        action_contract,
        particle_info,
        particle_tracker,
        position_quality_resolver,
    )


class DeadConstraintValidator:
    """Track constraint use during an Action and diagnose what remains unused."""

    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _tracker: particle_tracker.ParticleTracker
    _position_quality_resolver: position_quality_resolver.PositionQualityResolver
    _dead_constraint_tracker: dead_constraint_tracker.DeadConstraintTracker

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        tracker: particle_tracker.ParticleTracker,
        quality_resolver: position_quality_resolver.PositionQualityResolver,
    ):
        """Initialize with known definitions, particle state, and Quality resolution."""
        self._definition_results = definition_results
        self._tracker = tracker
        self._position_quality_resolver = quality_resolver
        self._dead_constraint_tracker = dead_constraint_tracker.DeadConstraintTracker()

    def register_implied_actions(
        self, quality_implications: tuple[ast.QualityImplicationStatement, ...]
    ):
        """Register implied Actions before analyzing the Action's statements."""
        for implication in quality_implications:
            implied_action = implication.typed_global_name
            if implied_action.name_type != ast.NameType.ACTION:
                continue
            self._dead_constraint_tracker.register_implied_action(implied_action)

    def register_position_constraints(self, position: ast.LocalPositionDefinition):
        """Register constraints when a local or interface Position is declared."""
        self._dead_constraint_tracker.register_position_constraints(
            position, self._definition_results
        )

    def mark_action_alive(
        self,
        action: ast.GlobalTypedNameReference,
        position: ast.PositionReference | None,
        parent_particle: particle_info.ParticleInfo | None,
    ):
        """Keep implied Actions and constraints alive when the Action triggers."""
        self._dead_constraint_tracker.mark_action_alive(
            action,
            position,
            parent_particle.origin_position if parent_particle is not None else None,
        )

    def mark_value_constraint_alive(self, position: ast.PositionReference):
        """Keep the value constraint on a used particle's origin position alive."""
        particle = self._tracker.get_occupant_or_none(position)
        if particle is not None and particle.qualities.value_type is not None:
            self._dead_constraint_tracker.mark_value_alive(
                particle.origin_position, particle.qualities.value_type
            )

    def _particle_origin_position(
        self, position: ast.PositionReference
    ) -> ast.PositionReference | None:
        occupancy = self._tracker.get_occupancy_info(position)
        if occupancy.occupant is None:
            return None
        return occupancy.occupant.origin_position

    def mark_referenced_position_constraints_alive(self, chain: ast.PositionReference):
        """Keep constraints alive when their child Positions are referenced."""
        if not self._dead_constraint_tracker.has_position_constraint_candidates():
            return
        parent_position_name_count: int | None = None
        for name_index, typed_name in enumerate(chain.typed_names):
            if (
                parent_position_name_count is not None
                and isinstance(typed_name, ast.GlobalTypedNameReference)
                and typed_name.name_type == ast.NameType.POSITION
                and self._dead_constraint_tracker.has_position_constraint_candidate(
                    typed_name
                )
            ):
                current_position = chain.position_prefix(parent_position_name_count)
                self._dead_constraint_tracker.mark_position_alive(
                    current_position,
                    self._particle_origin_position(current_position),
                    typed_name,
                )
            if typed_name.name_type == ast.NameType.POSITION:
                parent_position_name_count = name_index + 1

    def mark_callee_contract_constraints_alive(
        self,
        requirements_in_caller: list[action_contract.PositionRequirementInCaller],
        scope: scope_tracker.ScopeTracker,
    ):
        """Keep constraints alive through occupied callee requirements."""
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        for requirement_in_caller in requirements_in_caller:
            if (
                requirement_in_caller.requirement.required_state
                != position_occupancy.PositionOccupancyState.OCCUPIED
            ):
                continue
            occupancy = self._tracker.get_occupancy_info(
                requirement_in_caller.caller_position
            )
            if occupancy.occupant is None:
                continue
            self.mark_contract_position_constraints_alive(
                requirement_in_caller.caller_position, occupancy.occupant, scope
            )

    def mark_contract_position_constraints_alive(
        self,
        position: ast.PositionReference,
        particle: particle_info.ParticleInfo,
        scope: scope_tracker.ScopeTracker,
    ):
        """Keep a particle's origin constraints alive through a contracted Position."""
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        constraints = self._position_quality_resolver.get_direct_required_qualities(
            position, scope
        )
        if constraints is None:
            return
        self._dead_constraint_tracker.mark_contract_constraints_alive(
            None, particle.origin_position, constraints
        )

    def validate(
        self,
        own_guarantees: dict[ast.ChainedNameTuple, action_contract.PositionGuarantee],
        scope: scope_tracker.ScopeTracker,
    ) -> list[diagnostics.Diagnostic]:
        """Check dead constraints and untriggered Actions after accounting for final guarantees."""
        self._mark_own_contract_guarantees_alive(own_guarantees, scope)
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        for candidate in self._dead_constraint_tracker.dead_value_constraints():
            validation_diagnostics.append(
                diagnostics.DeadValueConstraintDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for candidate in self._dead_constraint_tracker.dead_position_constraints():
            validation_diagnostics.append(
                diagnostics.DeadChildPositionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for candidate in self._dead_constraint_tracker.dead_action_constraints():
            validation_diagnostics.append(
                diagnostics.UntriggeredActionDiagnostic(
                    location=candidate.constraint.location,
                    constraint_name=candidate.constraint.source_typed_name,
                    position_name=candidate.position.source_typed_name,
                )
            )
        for (
            implied_action
        ) in self._dead_constraint_tracker.untriggered_implied_actions():
            validation_diagnostics.append(
                diagnostics.UntriggeredImpliedActionDiagnostic(
                    location=implied_action.location,
                    implied_action_name=implied_action.source_typed_name,
                )
            )
        for position in self._tracker.dead_action_interface_arrivals():
            action = typing.cast(
                "ast.GlobalTypedNameReference", position.get_last_action()
            )
            validation_diagnostics.append(
                diagnostics.UntriggeredActionInterfaceDiagnostic(
                    location=action.location,
                    action_name=action.source_typed_name,
                    position_name=position.source_chained_name,
                )
            )
        return validation_diagnostics

    def _mark_own_contract_guarantees_alive(
        self,
        own_guarantees: dict[ast.ChainedNameTuple, action_contract.PositionGuarantee],
        scope: scope_tracker.ScopeTracker,
    ):
        """Keep origin and final position constraints alive through this action's guarantees."""
        if not self._dead_constraint_tracker.has_constraint_candidates():
            return
        for guarantee in own_guarantees.values():
            final_position = guarantee.caused_by
            origin_position = self._particle_origin_position(final_position)
            if origin_position is None:
                continue
            constraints = self._position_quality_resolver.get_direct_required_qualities(
                final_position, scope
            )
            constraints = typing.cast(
                "tuple[ast.GlobalTypedNameReference, ...]", constraints
            )
            self._dead_constraint_tracker.mark_contract_constraints_alive(
                final_position, origin_position, constraints
            )
