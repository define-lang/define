"""Validation of a Value Operation or Encoding Operation definition, and collection of a Value Operation's steps."""

from __future__ import annotations

import abc
import typing
from typing import override

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import scope_tracker, validation_result
from define.compiler.validator.reference_graph import (
    abstract_program,
    operation_arguments_validator,
    view_use_tracker,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence

    from define.compiler.data_structures import typed_name_dict


class _ViewArgument(typing.NamedTuple):
    """An Operation Argument Statement that looks at a view of the operation."""

    argument: ast.OperationArgumentStatement[ast.LookedAt]
    looking_at: ast.LocalTypedNameReference
    looked_at_view: ast.InterfaceViewDefinition | ast.LocalViewDefinition
    # The executed definition's view, if the executed definition defines it.
    executed_view: ast.ViewDefinition | None


class OperationDefinitionValidator[
    DefinitionT: ast.OperationDefinition,
    ResultT: validation_result.PostorderValidationResult,
](abc.ABC):
    """Validates the execution statements of an operation definition against the operations and logical operations they execute."""

    _definition: DefinitionT
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _diagnostics: list[diagnostics.Diagnostic]
    _arguments_validator: operation_arguments_validator.OperationArgumentsValidator
    _views: scope_tracker.ScopeTracker[
        ast.InterfaceViewDefinition | ast.LocalViewDefinition
    ]
    _view_uses: view_use_tracker.ViewUseTracker

    def __init__(
        self,
        definition: DefinitionT,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the Operation Definition and known definitions."""
        self._definition = definition
        self._definition_results = definition_results
        self._diagnostics = []
        self._views = scope_tracker.ScopeTracker()
        self._view_uses = view_use_tracker.ViewUseTracker()
        for view in definition.views:
            self._define_view(view)
        self._views.enter_child_scope()
        self._arguments_validator = (
            operation_arguments_validator.OperationArgumentsValidator(
                definition_results, definition.typed_name.name_content.fqun
            )
        )

    def analyze(self) -> ResultT:
        """Validate the definition and return its validation result."""
        for statement in self._definition.operation_statements.statements:
            self._view_uses.start_statement(statement)
            match statement:
                case ast.LocalViewDefinition():
                    self._define_view(statement)
                    self._add_local_statement(statement)
                case ast.OperationExecutionStatement():
                    self._analyze_operation_execution(statement)
                case ast.LogicalOperationExecutionStatement():
                    _ = self._analyze_logical_operation_execution(statement)
                case ast.ViewSettingStatement():
                    self._diagnostics.extend(
                        self._view_uses.record_view_setting(statement)
                    )
                    self._add_local_statement(statement)
                case ast.ComputerOperationExecutionStatement():
                    raise TypeError(
                        "Only an Encoding Operation's only statement may "
                        + "execute the computer operation"
                    )
        self._diagnostics.extend(self._view_uses.check_operation_end())
        return self._build_result()

    @abc.abstractmethod
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
    ): ...

    @abc.abstractmethod
    def _add_local_statement(
        self, statement: ast.LocalViewDefinition | ast.ViewSettingStatement
    ):
        """Record a statement that only uses the operation's own views."""

    @abc.abstractmethod
    def _build_result(self) -> ResultT: ...

    def _define_view(self, view: ast.InterfaceViewDefinition | ast.LocalViewDefinition):
        # Structural validation reports a view whose name is already defined.
        if not self._views.is_defined(view.typed_name):
            self._views.add_definition(view)
            self._view_uses.add_view(view)

    def _analyze_operation_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
    ):
        executed = self._arguments_validator.get_executed_operation(statement)
        if executed is None:
            self._mark_views_with_unknown_use(statement.arguments)
            return
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        operation_name = statement.operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        read_write_view = next(
            (view for view in executed.views if view.is_input and view.is_output),
            None,
        )
        if read_write_view is not None:
            statement_diagnostics.append(
                diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
                    location=statement.operation.location,
                    operation_name=operation_name,
                    view_name=read_write_view.typed_name.source_typed_name,
                )
            )
        looked_at_qualities: dict[
            ast.OperationArgumentStatement[ast.LookedAt], Collection[str]
        ] = {}
        for view_argument in self._record_view_arguments(
            statement.arguments, executed, operation_name, statement_diagnostics
        ):
            looked_at_qualities[view_argument.argument] = (
                view_argument.looked_at_view.quality_assignment_block.as_set
            )
        argument_diagnostics = self._arguments_validator.validate(
            statement, looked_at_qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        self._diagnostics.extend(statement_diagnostics)
        if not statement_diagnostics:
            self._analyze_valid_execution(statement, executed)

    def _analyze_logical_operation_execution(
        self, statement: ast.LogicalOperationExecutionStatement
    ) -> abstract_program.LogicalOperationExecution | None:
        """Validate a Logical Operation Execution Statement, and return the execution if it is valid."""
        executed = self._arguments_validator.get_executed_logical_operation(statement)
        if executed is None:
            self._mark_views_with_unknown_use(statement.arguments)
            return None
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        operation_name = statement.logical_operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        for view_argument in self._record_view_arguments(
            statement.arguments, executed, operation_name, statement_diagnostics
        ):
            statement_diagnostics.extend(
                self._unsupported_logical_operation_uses(
                    statement.logical_operation, operation_name, view_argument
                )
            )
        arguments_by_index = self._arguments_validator.validate_arguments(
            statement.logical_operation,
            statement.arguments,
            executed,
            operation_name,
            statement_diagnostics,
        )
        self._diagnostics.extend(statement_diagnostics)
        if statement_diagnostics:
            return None
        # Valid arguments name each of the logical operation's views once, in
        # order.
        arguments: list[
            abstract_program.Argument[
                ast.LogicalOperationViewDefinition, ast.LocalTypedNameReference
            ]
        ] = []
        for index, argument in arguments_by_index.items():
            arguments.append(
                abstract_program.Argument(
                    interface_view=executed.views[index],
                    looking_at=argument.looking_at,
                )
            )
        return abstract_program.LogicalOperationExecution(
            logical_operation=statement.logical_operation, arguments=arguments
        )

    def _record_view_arguments(
        self,
        arguments: Sequence[
            ast.OperationArgumentStatement[ast.LocalTypedNameReference | ast.Literal]
        ],
        executed: ast.ExecutableDefinition[ast.ViewDefinition],
        operation_name: str,
        statement_diagnostics: list[diagnostics.Diagnostic],
    ) -> Iterator[_ViewArgument]:
        """Record how the executed definition uses each view the arguments look at, and yield each argument that looks at a view."""
        view_indexes = executed.view_indexes_by_name()
        for argument in arguments:
            looking_at = argument.looking_at
            # Literals are checked when the arguments are validated.
            if not isinstance(looking_at, ast.LocalTypedNameReference):
                continue
            looked_at_view = self._views.get_definition_or_none(looking_at)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            view_index = view_indexes.get(argument.view.source_typed_name)
            executed_view = None if view_index is None else executed.views[view_index]
            statement_diagnostics.extend(
                self._view_uses.record_use(
                    argument, looking_at, executed_view, operation_name
                )
            )
            yield _ViewArgument(argument, looking_at, looked_at_view, executed_view)

    def _unsupported_logical_operation_uses(
        self,
        logical_operation: ast.GlobalTypedNameReference,
        operation_name: str,
        view_argument: _ViewArgument,
    ) -> list[diagnostics.Diagnostic]:
        """Return a diagnostic for each direction the logical operation's view uses that the looked-at view's value quality does not support."""
        logical_operation_view = view_argument.executed_view
        # An undefined view of the logical operation is reported when the
        # arguments are validated.
        if logical_operation_view is None:
            return []
        value_quality = (
            view_argument.looked_at_view.quality_assignment_block.value_quality
        )
        # Structural validation reports views without a value quality.
        if value_quality is None:
            return []
        value_result = self._definition_results.get(value_quality)
        # A missing value, or a definition of another type, was already
        # reported when its reference was resolved.
        if value_result is None:
            return []
        value_definition = typing.cast("ast.ValueDefinition", value_result.definition)
        may_be_read = False
        may_be_written = False
        for support in value_definition.logical_operation_support_statements:
            if (
                support.logical_operation.full_typed_name
                == logical_operation.full_typed_name
            ):
                may_be_read = support.may_be_read
                may_be_written = support.may_be_written
                break
        value_name = value_quality.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        looking_at = view_argument.looking_at
        support_diagnostics: list[diagnostics.Diagnostic] = []
        if logical_operation_view.is_input and not may_be_read:
            support_diagnostics.append(
                diagnostics.LogicalOperationReadNotSupportedDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    logical_operation_name=operation_name,
                    value_name=value_name,
                )
            )
        if logical_operation_view.is_output and not may_be_written:
            support_diagnostics.append(
                diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    logical_operation_name=operation_name,
                    value_name=value_name,
                )
            )
        return support_diagnostics

    def _mark_views_with_unknown_use(
        self, arguments: Sequence[ast.OperationArgumentStatement[ast.LookedAt]]
    ):
        """Mark the views the arguments look at as having unknown use, because the executed definition is missing."""
        for argument in arguments:
            looking_at = argument.looking_at
            if isinstance(looking_at, ast.LocalTypedNameReference):
                self._view_uses.mark_unknown_use(looking_at)


class ValueOperationDefinitionValidator(
    OperationDefinitionValidator[
        ast.ValueOperationDefinition,
        validation_result.ValueOperationPostorderValidationResult,
    ]
):
    """Validates a Value Operation definition and collects its steps, which are independent of the encodings of what an execution of it looks at."""

    _steps: list[abstract_program.ValueOperationStep]

    def __init__(
        self,
        definition: ast.ValueOperationDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the Value Operation Definition and known definitions."""
        super().__init__(definition, definition_results)
        self._steps = []

    @override
    def _analyze_logical_operation_execution(
        self, statement: ast.LogicalOperationExecutionStatement
    ) -> abstract_program.LogicalOperationExecution | None:
        execution = super()._analyze_logical_operation_execution(statement)
        if execution is not None:
            self._steps.append(execution)
        return execution

    @override
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
    ):
        # The grammar allows a Value Operation to execute only Value
        # Operations, whose literals are encoded during association
        # resolution.
        value_operation = typing.cast("ast.ValueOperationDefinition", executed)
        arguments = self._arguments_validator.value_operation_arguments(
            statement, value_operation
        )
        if arguments is not None:
            self._steps.append(
                abstract_program.ValueOperationExecution(
                    value_operation=value_operation,
                    operation=statement.operation,
                    arguments=arguments,
                )
            )

    @override
    def _add_local_statement(
        self, statement: ast.LocalViewDefinition | ast.ViewSettingStatement
    ):
        self._steps.append(statement)

    def _has_diagnostics(self) -> bool:
        """Whether either validation phase reported anything about the Value Operation."""
        # Structural validation also reports problems that leave the steps
        # unusable, such as an execution that looks at an undefined view.
        return bool(
            self._diagnostics
            or self._definition_results[self._definition.typed_name].diagnostics
        )

    @override
    def _build_result(
        self,
    ) -> validation_result.ValueOperationPostorderValidationResult:
        return validation_result.ValueOperationPostorderValidationResult(
            diagnostics=self._diagnostics,
            steps=None if self._has_diagnostics() else self._steps,
        )
