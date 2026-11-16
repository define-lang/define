"""Validate an action's Operation Execution Statements."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.validator.reference_graph import (
    abstract_program,
    operation_arguments_validator,
    position_occupancy,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.errors import diagnostics
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        action_requirement_validator,
        chained_name_validator,
        particle_operation_validator,
    )
    from define.compiler.validator.reference_graph.dead_code import (
        dead_quality_assignment_validator,
        dead_value_write_validator,
    )
    from define.compiler.validator.reference_graph.particles import particle_tracker


class _LookedAtPositions(msgspec.Struct):
    """What the positions that an Operation Execution Statement's arguments look at hold, and how the statement uses them."""

    qualities: dict[ast.OperationArgumentStatement[ast.LookedAt], Collection[str]] = (
        msgspec.field(default_factory=dict)
    )
    # Keyed by the source typed name of the interface view that looks at the
    # position.
    value_qualities: dict[str, ast.GlobalTypedNameReference] = msgspec.field(
        default_factory=dict
    )
    written_positions: list[ast.PositionReference] = msgspec.field(default_factory=list)
    positions_with_unknown_use: list[ast.PositionReference] = msgspec.field(
        default_factory=list
    )


@typing.final
class ActionOperationExecutionValidator:
    """Validates the Operation Execution Statements of one action."""

    def __init__(
        self,
        action: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        tracker: particle_tracker.ParticleTracker,
        chained_name_validator: chained_name_validator.ChainedNameValidator,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
        dead_quality_assignment_validator: dead_quality_assignment_validator.DeadQualityAssignmentValidator,
        dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator,
        operation_validator: particle_operation_validator.ParticleOperationValidator,
    ):
        """Initialize with the action, the known definitions, and the action validator's collaborators that every statement of the action shares."""
        self._enclosing_fqun = action.typed_name.name_content.fqun
        self._tracker = tracker
        self._chained_name_validator = chained_name_validator
        self._requirement_validator = requirement_validator
        self._dead_quality_assignment_validator = dead_quality_assignment_validator
        self._dead_value_write_validator = dead_value_write_validator
        self._operation_validator = operation_validator
        self._arguments_validator = (
            operation_arguments_validator.OperationArgumentsValidator(
                definition_results, self._enclosing_fqun
            )
        )

    def validate(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        looked_at_validity: Iterator[bool],
        scope: scope_tracker.PositionScopeTracker,
    ) -> tuple[
        list[diagnostics.Diagnostic], abstract_program.ActionOperationExecution | None
    ]:
        """Validate an Operation Execution Statement, and return its diagnostics and, if it is valid, its step."""
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        executed = self._arguments_validator.get_executed_operation(stmt)
        looked_at = self._analyze_looked_at_positions(
            stmt, executed, looked_at_validity, scope, statement_diagnostics
        )
        argument_diagnostics = self._arguments_validator.validate(
            stmt, looked_at.qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        is_valid = not statement_diagnostics
        statement_diagnostics.extend(
            self._record_value_uses(looked_at, is_valid=is_valid)
        )
        if executed is None or not is_valid:
            return statement_diagnostics, None
        # Actions can only execute Value Operations.
        value_operation = typing.cast("ast.ValueOperationDefinition", executed)
        arguments = self._arguments_validator.value_operation_arguments(
            stmt, value_operation
        )
        if arguments is None:
            return statement_diagnostics, None
        step = abstract_program.ActionOperationExecution(
            operation=stmt.operation,
            value_operation=value_operation,
            arguments=arguments,
            looked_at_value_qualities=looked_at.value_qualities,
        )
        return statement_diagnostics, step

    def _analyze_looked_at_positions(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        executed: ast.OperationDefinition | None,
        looked_at_validity: Iterator[bool],
        scope: scope_tracker.PositionScopeTracker,
        statement_diagnostics: list[diagnostics.Diagnostic],
    ) -> _LookedAtPositions:
        """Validate the positions that the statement's arguments look at, and return what they hold and how the statement uses them.

        Diagnostics are added to ``statement_diagnostics``.
        """
        looked_at = _LookedAtPositions()
        view_indexes = {} if executed is None else executed.view_indexes_by_name()
        for argument in stmt.arguments:
            position = argument.looking_at
            if not isinstance(position, ast.PositionReference):
                continue
            if not next(looked_at_validity):
                continue
            view_index = view_indexes.get(argument.view.source_typed_name)
            interface_view = (
                None
                if executed is None or view_index is None
                else executed.views[view_index]
            )
            is_read = interface_view is not None and interface_view.is_input
            particle = self._analyze_looked_at_position(
                position, scope, statement_diagnostics, is_read=is_read
            )
            if particle is None:
                continue
            looked_at.qualities[argument] = particle.qualities.names
            if particle.qualities.value_quality is None:
                continue
            looked_at.value_qualities[argument.view.source_typed_name] = (
                particle.qualities.value_quality
            )
            # A missing operation or an undefined interface view is reported
            # when the arguments are validated, so whether this statement
            # reads or writes its position is unknown.
            if interface_view is None:
                looked_at.positions_with_unknown_use.append(position)
            elif interface_view.is_output:
                looked_at.written_positions.append(position)
        return looked_at

    def _analyze_looked_at_position(
        self,
        position: ast.PositionReference,
        scope: scope_tracker.PositionScopeTracker,
        statement_diagnostics: list[diagnostics.Diagnostic],
        *,
        is_read: bool,
    ) -> particle_info.ParticleInfo | None:
        """Validate a position looked at by an Operation Argument Statement, and return its particle when it can be checked further.

        Diagnostics are added to ``statement_diagnostics``.
        """
        self._dead_quality_assignment_validator.mark_referenced_child_positions_alive(
            position
        )
        statement_diagnostics.extend(
            self._chained_name_validator.validate(position, scope)
        )
        if self._tracker.has_error_state(position):
            return None
        self._requirement_validator.infer_requirements_on_chain(
            position_occupancy.PositionOccupancyState.OCCUPIED, position, scope
        )
        self._dead_quality_assignment_validator.mark_value_and_encoding_alive(position)
        if is_read:
            self._requirement_validator.infer_value_requirement(
                position, inferred_at=position.location
            )
            self._dead_value_write_validator.mark_used(position)
        diagnostic = self._operation_validator.validate_looked_at(
            position, is_read=is_read
        )
        if diagnostic is not None:
            statement_diagnostics.append(diagnostic)
        return self._tracker.get_occupant_or_none(position)

    def _record_value_uses(
        self, looked_at: _LookedAtPositions, *, is_valid: bool
    ) -> list[diagnostics.Diagnostic]:
        """Record how the statement used the values of the positions it looks at, and return the diagnostics about its writes."""
        # The statement may have read the value of a position with unknown
        # use, or written it, so neither an earlier write nor a later read
        # reports the same mistake again.
        for position in looked_at.positions_with_unknown_use:
            self._dead_value_write_validator.mark_used(position)
            self._tracker.mark_value_error(position)
        write_diagnostics: list[diagnostics.Diagnostic] = []
        # A failed statement still counts as writing its output views, so
        # later reads do not report the same mistake again as an unset value.
        for position in looked_at.written_positions:
            if is_valid:
                self._tracker.set_value(position, particle_info.ParticleValueState.SET)
                write_diagnostics.extend(
                    self._dead_value_write_validator.record_write(position)
                )
            else:
                self._tracker.mark_value_error(position)
        return write_diagnostics
