"""Reference graph validation of a Value Operation or Encoding Operation definition."""

from __future__ import annotations

import abc
import typing
from typing import override

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input, scope_tracker, validation_result
from define.compiler.validator.reference_graph import (
    literal_encoder,
    operation_arguments_validator,
    view_use_tracker,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Mapping, Sequence

    from define.compiler.data_structures import typed_name_dict


class _ViewArgument(typing.NamedTuple):
    """An Operation Argument Statement that looks at a view of the operation."""

    argument: ast.OperationArgumentStatement[ast.LookedAt]
    looking_at: ast.LocalTypedNameReference
    looked_at_view: ast.InterfaceViewDefinition | ast.LocalViewDefinition
    # The executed definition's view, if the executed definition defines it.
    executed_view: ast.ViewDefinition | None


class OperationDefinitionValidator[DefinitionT: ast.OperationDefinition](abc.ABC):
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
        self._view_uses = view_use_tracker.ViewUseTracker(
            definition.typed_name.name_type
        )
        for view in definition.views:
            self._define_view(view)
        self._views.enter_child_scope()
        enclosing_fqun = definition.typed_name.name_content.fqun
        self._arguments_validator = (
            operation_arguments_validator.OperationArgumentsValidator(
                definition_results,
                enclosing_fqun,
                literal_encoder.LiteralEncoder(definition_results, enclosing_fqun),
            )
        )

    def analyze(self) -> validation_result.PostorderValidationResult:
        """Validate the definition and return its validation result."""
        for statement in self._definition.operation_statements.statements:
            match statement:
                case ast.LocalViewDefinition():
                    self._define_view(statement)
                case ast.OperationExecutionStatement():
                    self._analyze_operation_execution(statement)
                case ast.LogicalOperationExecutionStatement():
                    self._analyze_logical_operation_execution(statement)
                case (
                    ast.EncodingOperationExecutionStatement()
                    | ast.ComputerOperationExecutionStatement()
                ):
                    self._analyze_encoding_or_computer_operation_execution(statement)
        self._diagnostics.extend(self._view_uses.check_operation_end())
        return self._build_result()

    @abc.abstractmethod
    def _analyze_encoding_or_computer_operation_execution(
        self,
        statement: ast.EncodingOperationExecutionStatement
        | ast.ComputerOperationExecutionStatement,
    ): ...

    @abc.abstractmethod
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], codegen_input.EncodedLiteral
        ],
    ): ...

    @abc.abstractmethod
    def _build_result(self) -> validation_result.PostorderValidationResult: ...

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
        looked_at_qualities: dict[
            ast.OperationArgumentStatement[ast.LookedAt], Collection[str]
        ] = {}
        for view_argument in self._record_view_arguments(
            statement.arguments, executed, operation_name, statement_diagnostics
        ):
            looked_at_qualities[view_argument.argument] = (
                view_argument.looked_at_view.quality_assignment_block.as_set
            )
        argument_diagnostics, literal_values = self._arguments_validator.validate(
            statement, looked_at_qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        self._diagnostics.extend(statement_diagnostics)
        if not statement_diagnostics:
            self._analyze_valid_execution(statement, executed, literal_values)

    def _analyze_logical_operation_execution(
        self, statement: ast.LogicalOperationExecutionStatement
    ):
        executed = self._arguments_validator.get_executed_logical_operation(statement)
        if executed is None:
            self._mark_views_with_unknown_use(statement.arguments)
            return
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
        _ = self._arguments_validator.validate_arguments(
            statement.logical_operation,
            statement.arguments,
            executed,
            operation_name,
            statement_diagnostics,
        )
        self._diagnostics.extend(statement_diagnostics)

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
        for argument in arguments:
            looking_at = argument.looking_at
            # Literals are checked when the arguments are validated.
            if not isinstance(looking_at, ast.LocalTypedNameReference):
                continue
            looked_at_view = self._views.get_definition_or_none(looking_at)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            executed_view = executed.get_view(argument.view.source_typed_name)
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
    OperationDefinitionValidator[ast.ValueOperationDefinition]
):
    """Validates a Value Operation definition."""

    @override
    def _analyze_encoding_or_computer_operation_execution(
        self,
        statement: ast.EncodingOperationExecutionStatement
        | ast.ComputerOperationExecutionStatement,
    ):
        self._view_uses.fulfill_every_interface_view_direction(statement.location)

    @override
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], codegen_input.EncodedLiteral
        ],
    ):
        # Value Operations have no code of their own: executing one runs the
        # Encoding Operation that performs it.
        pass

    @override
    def _build_result(self) -> validation_result.PostorderValidationResult:
        return validation_result.PostorderValidationResult(self._diagnostics)


class EncodingOperationDefinitionValidator(
    OperationDefinitionValidator[ast.EncodingOperationDefinition]
):
    """Validates an Encoding Operation definition and collects its steps for code generation."""

    _steps: list[codegen_input.EncodingOperationStep]

    def __init__(
        self,
        definition: ast.EncodingOperationDefinition,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the Encoding Operation Definition and known definitions."""
        super().__init__(definition, definition_results)
        self._steps = []

    @override
    def _analyze_encoding_or_computer_operation_execution(
        self,
        statement: ast.EncodingOperationExecutionStatement
        | ast.ComputerOperationExecutionStatement,
    ):
        # TODO: Once users can define Encoding Operations that associate with
        # Value Operations, report a computer operation that the compiler
        # cannot perform. Code generation relies on performing every one.
        self._view_uses.fulfill_every_interface_view_direction(statement.location)
        # The grammar allows only computer operations in an Encoding
        # Operation.
        self._steps.append(
            typing.cast("ast.ComputerOperationExecutionStatement", statement)
        )

    @override
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], codegen_input.EncodedLiteral
        ],
    ):
        arguments = self._arguments_validator.operation_arguments(
            statement, executed, literal_values
        )
        if arguments is not None:
            self._steps.append(
                codegen_input.EncodingOperationExecution(
                    encoding_operation=statement.operation, arguments=arguments
                )
            )

    @override
    def _build_result(self) -> validation_result.PostorderValidationResult:
        return validation_result.EncodingOperationPostorderValidationResult(
            diagnostics=self._diagnostics,
            codegen_input=codegen_input.EncodingOperationCodegenInput(
                definition=self._definition, steps=self._steps
            ),
        )
