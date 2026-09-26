"""Validate Particle Operations against tracked Position state."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics
from define.compiler.validator.reference_graph import particle_info

if typing.TYPE_CHECKING:
    from define.compiler.validator.reference_graph import particle_tracker


class ParticleOperationValidator:
    """Check whether Particle Operations are valid."""

    _tracker: particle_tracker.ParticleTracker
    _enclosing_fqun: ast.Fqun

    def __init__(
        self, tracker: particle_tracker.ParticleTracker, enclosing_fqun: ast.Fqun
    ):
        """Validate against this action's tracked Position state."""
        self._tracker = tracker
        self._enclosing_fqun = enclosing_fqun

    def validate_create(
        self, target: ast.PositionReference
    ) -> diagnostics.Diagnostic | None:
        """Validate a Create."""
        parent_diagnostic = self._check_parents_occupied(target)
        if parent_diagnostic is not None:
            self._tracker.mark_error(target)
            return parent_diagnostic
        particle = self._tracker.get_occupant_or_none(target)
        if particle is not None:
            # Target is genuinely occupied — leave its known state intact so
            # later statements can still reason about the existing particle.
            return diagnostics.CreateInOccupiedPositionDiagnostic(
                location=target.location,
                position_name=target.source_chained_name,
                populated_at=particle.last_position.location,
            )
        return None

    def validate_move(
        self,
        source: ast.PositionReference,
        target: ast.PositionReference,
        target_required_qualities: tuple[ast.GlobalTypedNameReference, ...],
    ) -> list[diagnostics.Diagnostic]:
        """Validate a Move."""
        parent_diags: list[diagnostics.Diagnostic] = []
        for position in (source, target):
            parent_diagnostic = self._check_parents_occupied(position)
            if parent_diagnostic is not None:
                parent_diags.append(parent_diagnostic)
        if parent_diags:
            self._tracker.mark_error(source)
            self._tracker.mark_error(target)
            return parent_diags
        source_particle = self._tracker.get_occupant_or_none(source)
        target_particle = self._tracker.get_occupant_or_none(target)
        diags: list[diagnostics.Diagnostic] = []
        if source_particle is None:
            from_action = source.get_last_action()
            is_action_interface_position = from_action is not None
            emptied_by = (
                self._tracker.get_emptied_by(source)
                if is_action_interface_position
                else None
            )
            diags.append(
                diagnostics.MoveFromEmptyPositionDiagnostic(
                    location=source.location,
                    position_name=source.source_chained_name,
                    is_action_interface_position=is_action_interface_position,
                    inferred_at=emptied_by.location if emptied_by else None,
                )
            )
        if target_particle is not None:
            diags.append(
                diagnostics.MoveToOccupiedPositionDiagnostic(
                    location=target.location,
                    position_name=target.source_chained_name,
                    occupied_at=target_particle.last_position.location,
                )
            )
        if source_particle is None or target_particle is not None:
            self._tracker.mark_error(source)
            self._tracker.mark_error(target)
            return diags
        have = source_particle.qualities
        missing = [
            name.source_form_in_universe(self._enclosing_fqun)
            for name in target_required_qualities
            if not have.has_quality(name)
        ]
        if missing:
            self._tracker.mark_error(source)
            self._tracker.mark_error(target)
            return [
                diagnostics.MoveViolatesConstraintsDiagnostic(
                    location=target.location,
                    source_position=source.source_chained_name,
                    target_position=target.source_chained_name,
                    missing_qualities=missing,
                )
            ]
        return []

    def validate_value_setting(
        self, target: ast.PositionReference, source: ast.PositionReference | ast.Literal
    ) -> tuple[list[diagnostics.Diagnostic], particle_info.ParticleValueState]:
        """Validate occupancy and assigned value types for a Value Setting Statement."""
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        target_type = self._validate_value_setting_position(
            target, validation_diagnostics
        )
        if isinstance(source, ast.Literal):
            return validation_diagnostics, particle_info.ParticleValueState.SET
        source_type = self._validate_value_setting_position(
            source, validation_diagnostics
        )
        if source_type is None:
            return validation_diagnostics, particle_info.ParticleValueState.ERROR
        if (
            target_type is not None
            and target_type.full_typed_name != source_type.full_typed_name
        ):
            validation_diagnostics.append(
                diagnostics.ValueSettingTypeMismatchDiagnostic(
                    location=source.location,
                    target_position=target.source_chained_name,
                    source_position=source.source_chained_name,
                    target_value_type=target_type.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    source_value_type=source_type.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                )
            )
        particle = self._tracker.get_occupant(source)
        value_state = particle.value_state
        if value_state not in (
            particle_info.ParticleValueState.SET,
            particle_info.ParticleValueState.ERROR,
        ):
            validation_diagnostics.append(
                diagnostics.UnsetValueDiagnostic(
                    location=source.location,
                    position_name=source.source_chained_name,
                )
            )
            value_state = particle_info.ParticleValueState.ERROR
            self._tracker.mark_value_error(source)
            if target_type is not None:
                self._tracker.mark_value_error(target)
        return validation_diagnostics, value_state

    def _validate_value_setting_position(
        self,
        position: ast.PositionReference,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> ast.GlobalTypedNameReference | None:
        """Validate a position used in a Value Setting Statement."""
        if self._tracker.has_error_state(position):
            return None
        parent_diagnostic = self._check_parents_occupied(position)
        if parent_diagnostic is not None:
            validation_diagnostics.append(parent_diagnostic)
            return None
        particle = self._tracker.get_occupant_or_none(position)
        if particle is None:
            validation_diagnostics.append(
                diagnostics.ValueSettingEmptyPositionDiagnostic(
                    location=position.location,
                    position_name=position.source_chained_name,
                )
            )
            return None
        value_type = particle.qualities.value_type
        if value_type is None:
            validation_diagnostics.append(
                diagnostics.ValueSettingMissingValueTypeDiagnostic(
                    location=position.location,
                    position_name=position.source_chained_name,
                    origin_position_name=particle.origin_position.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                )
            )
        return value_type

    def validate_destroy(
        self,
        target: ast.PositionReference,
    ) -> diagnostics.Diagnostic | None:
        """Validate a Destroy."""
        parent_diagnostic = self._check_parents_occupied(target)
        if parent_diagnostic is not None:
            self._tracker.mark_error(target)
            return parent_diagnostic
        if not self._tracker.is_occupied(target):
            self._tracker.mark_error(target)
            from_action = target.get_last_action()
            if from_action is not None:
                emptied_by = self._tracker.get_emptied_by(target)
                return diagnostics.DestroyInEmptyInterfacePositionDiagnostic(
                    location=target.location,
                    position_name=target.source_chained_name,
                    inferred_at=emptied_by.location if emptied_by else None,
                )
            return diagnostics.DestroyInEmptyPositionDiagnostic(
                location=target.location,
                position_name=target.source_chained_name,
            )
        return None

    def _check_parents_occupied(
        self, target: ast.PositionReference
    ) -> diagnostics.ParentPositionNotOccupiedDiagnostic | None:
        """Report the first unoccupied parent position in chained-name order."""
        parent_position = self._tracker.first_unoccupied_parent(target)
        if parent_position is None:
            return None
        return diagnostics.ParentPositionNotOccupiedDiagnostic(
            location=target.location,
            position_name=target.source_chained_name,
            parent_position_name=parent_position.source_chained_name,
        )
