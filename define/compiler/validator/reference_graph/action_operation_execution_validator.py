"""Validate an action's Operation Execution Statements and choose the Encoding Operations they run."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input
from define.compiler.validator.reference_graph import (
    operation_arguments_validator,
    position_occupancy,
    value_operation_executions,
)
from define.compiler.validator.reference_graph.particles import particle_info

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping, Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import scope_tracker, validation_result
    from define.compiler.validator.reference_graph import (
        action_requirement_validator,
        chained_name_validator,
        literal_encoder,
        particle_operation_validator,
        reference_graph_validation_state,
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
    """Validates the Operation Execution Statements of one action, and chooses the Encoding Operations that they run."""

    def __init__(
        self,
        action: ast.ActionDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        validation_state: reference_graph_validation_state.ReferenceGraphValidationState,
        value_operation_executions: value_operation_executions.ValueOperationExecutions,
        tracker: particle_tracker.ParticleTracker,
        chained_name_validator: chained_name_validator.ChainedNameValidator,
        requirement_validator: action_requirement_validator.ActionRequirementValidator,
        dead_quality_assignment_validator: dead_quality_assignment_validator.DeadQualityAssignmentValidator,
        dead_value_write_validator: dead_value_write_validator.DeadValueWriteValidator,
        operation_validator: particle_operation_validator.ParticleOperationValidator,
        literal_encoder: literal_encoder.LiteralEncoder,
    ):
        """Initialize with the action, the known definitions, the shared validation state, what executing each Value Operation runs, and the action validator's collaborators that every statement of the action shares."""
        self._action = action.typed_name
        self._enclosing_fqun = action.typed_name.name_content.fqun
        self._validation_state = validation_state
        self._value_operation_executions = value_operation_executions
        self._tracker = tracker
        self._chained_name_validator = chained_name_validator
        self._requirement_validator = requirement_validator
        self._dead_quality_assignment_validator = dead_quality_assignment_validator
        self._dead_value_write_validator = dead_value_write_validator
        self._operation_validator = operation_validator
        self._arguments_validator = (
            operation_arguments_validator.OperationArgumentsValidator(
                definition_results, self._enclosing_fqun, literal_encoder
            )
        )

    def validate(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        looked_at_validity: Iterator[bool],
        scope: scope_tracker.PositionScopeTracker,
    ) -> tuple[
        list[diagnostics.Diagnostic], codegen_input.ActionOperationExecution | None
    ]:
        """Validate an Operation Execution Statement, and return its diagnostics and, if it is valid and its Encoding Operations can be chosen, its code generation step."""
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        executed = self._arguments_validator.get_executed_operation(stmt)
        looked_at = self._analyze_looked_at_positions(
            stmt, executed, looked_at_validity, scope, statement_diagnostics
        )
        argument_diagnostics, literal_values = self._arguments_validator.validate(
            stmt, looked_at.qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        is_valid = not statement_diagnostics
        statement_diagnostics.extend(
            self._record_value_uses(looked_at, is_valid=is_valid)
        )
        if executed is None or not is_valid:
            return statement_diagnostics, None
        step, step_diagnostics = self._operation_execution_step(
            stmt,
            # Actions can only execute Value Operations.
            typing.cast("ast.ValueOperationDefinition", executed),
            literal_values,
            looked_at.value_qualities,
        )
        statement_diagnostics.extend(step_diagnostics)
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

    def _operation_execution_step(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        executed: ast.ValueOperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], codegen_input.EncodedLiteral
        ],
        looked_at_value_qualities: Mapping[str, ast.GlobalTypedNameReference],
    ) -> tuple[
        codegen_input.ActionOperationExecution | None, list[diagnostics.Diagnostic]
    ]:
        """Return the code generation step of a valid Operation Execution Statement, if Encoding Operations can be chosen for it, and the diagnostics about choosing them."""
        arguments = self._arguments_validator.operation_arguments(
            stmt, executed, literal_values
        )
        if arguments is None:
            return None, []
        execution, execution_diagnostics = self._choose_encoding_operations(
            stmt, executed, arguments, looked_at_value_qualities
        )
        if execution is None:
            return None, execution_diagnostics
        return codegen_input.ActionOperationExecution(
            operation=stmt.operation,
            operation_arguments=arguments,
            runtime_operation=execution.runtime_operation,
            arguments=execution.arguments_for(arguments),
        ), execution_diagnostics

    def _choose_encoding_operations(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        executed: ast.ValueOperationDefinition,
        arguments: Sequence[codegen_input.OperationArgument[ast.PositionReference]],
        looked_at_value_qualities: Mapping[str, ast.GlobalTypedNameReference],
    ) -> tuple[
        codegen_input.OperationExecution | None,
        list[diagnostics.Diagnostic],
    ]:
        """Choose the Encoding Operations that executing the Value Operation runs for the encodings of what the arguments look at, and return what it runs, with a diagnostic if a logical operation it executes has no Encoding Operation for them."""
        view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for argument in arguments:
            looking_at = argument.looking_at
            view_name = argument.interface_view.typed_name.source_typed_name
            if isinstance(looking_at, codegen_input.EncodedLiteral):
                view_encodings[view_name] = looking_at.encoding
                continue
            value_quality = looked_at_value_qualities.get(view_name)
            # A looked-at position whose value quality is unknown was already
            # reported.
            if value_quality is None:
                return None, []
            encoding = self._validation_state.get_value_encoding(value_quality)
            # TODO: Report an interface view whose value quality has no
            # encoding when its Value Operation is validated. A position has
            # the value quality of the view that looks at it, so every
            # execution would give the same answer. Code generation relies on
            # every executed Value Operation having its Encoding Operations
            # chosen.
            if encoding is None:
                return None, []
            view_encodings[view_name] = encoding
        result = self._value_operation_executions.choose_encoding_operations(
            executed, view_encodings
        )
        if isinstance(result, value_operation_executions.MissingEncodingOperation):
            return None, [
                diagnostics.MissingEncodingOperationDiagnostic(
                    location=stmt.operation.location,
                    logical_operation_name=result.logical_operation.source_form_in_universe(
                        self._enclosing_fqun
                    ),
                    view_encodings=self._source_form_view_encodings(result),
                    execution_stack=self._execution_stack(stmt, result),
                )
            ]
        return result, []

    def _source_form_view_encodings(
        self, missing: value_operation_executions.MissingEncodingOperation
    ) -> dict[str, str]:
        """Return the encoding of each of the logical operation's views as it would be written in the action's universe, keyed by the view's source typed name."""
        view_encodings: dict[str, str] = {}
        for view, encoding in missing.view_encodings.items():
            view_encodings[view] = encoding.source_form_in_universe(
                self._enclosing_fqun
            )
        return view_encodings

    def _execution_stack(
        self,
        stmt: ast.OperationExecutionStatement[ast.PositionReference | ast.Literal],
        missing: value_operation_executions.MissingEncodingOperation,
    ) -> list[diagnostics.OperationExecutionStep]:
        """Return the executions from the action down to the Logical Operation Execution Statement that no Encoding Operation performs, in the order they happen."""
        stack: list[diagnostics.OperationExecutionStep] = []
        # Each execution is in the operation that the one before it executes.
        executing_name = self._action.source_typed_name
        for executed in (stmt.operation, *missing.execution_stack):
            executed_name = executed.source_form_in_universe(self._enclosing_fqun)
            stack.append(
                diagnostics.OperationExecutionStep(
                    executing_name=executing_name,
                    executed_name=executed_name,
                    location=executed.location,
                )
            )
            executing_name = executed_name
        return stack
