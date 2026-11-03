"""Reference graph validation of a Value Operation or Encoding Operation definition."""

from __future__ import annotations

import abc
import typing
from typing import override

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import codegen_input, validation_result
from define.compiler.validator.reference_graph import (
    literal_encoder,
    operation_arguments_validator,
)

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from define.compiler.data_structures import typed_name_dict


class OperationDefinitionValidator[DefinitionT: ast.OperationDefinition](abc.ABC):
    """Validates the execution statements of an operation definition against the operations and logical operations they execute."""

    _definition: DefinitionT
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _diagnostics: list[diagnostics.Diagnostic]
    _arguments_validator: operation_arguments_validator.OperationArgumentsValidator
    _read_views: set[str]
    _written_views: set[str]
    # Views looked at for a missing executed definition, or by a view the
    # executed definition does not define, so whether they are read or written
    # is unknown.
    _views_with_unknown_use: set[str]
    # Views a statement read or wrote against their direction. Fixing that
    # statement also fixes the view's unread or unwritten direction, so the
    # mistake is reported only once.
    _misused_views: set[str]

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
        self._read_views = set()
        self._written_views = set()
        self._views_with_unknown_use = set()
        self._misused_views = set()
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
        for statement in self._definition.operation_statements:
            match statement:
                case ast.OperationExecutionStatement():
                    self._analyze_operation_execution(statement)
                case ast.LogicalOperationExecutionStatement():
                    self._analyze_logical_operation_execution(statement)
                case (
                    ast.EncodingOperationExecutionStatement()
                    | ast.ComputerOperationExecutionStatement()
                ):
                    self._analyze_encoding_or_computer_operation_execution(statement)
        self._check_view_directions_fulfilled()
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

    def _fulfill_every_view_direction(self):
        for view in self._definition.views:
            view_name = view.typed_name.source_typed_name
            if view.is_input:
                self._read_views.add(view_name)
            if view.is_output:
                self._written_views.add(view_name)

    def _check_view_directions_fulfilled(self):
        for index, view in enumerate(self._definition.views):
            view_name = view.typed_name.source_typed_name
            # Structural validation reports duplicate views.
            if self._definition.view_index(view_name) != index:
                continue
            if (
                view_name in self._views_with_unknown_use
                or view_name in self._misused_views
            ):
                continue
            # Structural validation reports views that are never referenced.
            if (
                view_name not in self._read_views
                and view_name not in self._written_views
            ):
                continue
            if view.is_input and view_name not in self._read_views:
                self._diagnostics.append(
                    diagnostics.UnreadInputViewDiagnostic(
                        location=view.typed_name.name_content.location,
                        view_name=view_name,
                        operation_name_type=self._definition.typed_name.name_type,
                    )
                )
            if view.is_output and view_name not in self._written_views:
                self._diagnostics.append(
                    diagnostics.UnwrittenOutputViewDiagnostic(
                        location=view.typed_name.name_content.location,
                        view_name=view_name,
                        operation_name_type=self._definition.typed_name.name_type,
                    )
                )

    def _analyze_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        dict[
            ast.OperationArgumentStatement[ast.LookedAt], codegen_input.EncodedLiteral
        ],
    ]:
        """Validate an Operation Execution Statement, and return its diagnostics and its translated literals."""
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        operation_name = statement.operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        looked_at_qualities: dict[
            ast.OperationArgumentStatement[ast.LookedAt], Collection[str]
        ] = {}
        for argument in statement.arguments:
            looking_at = argument.looking_at
            # Literals are checked when the arguments are validated.
            if not isinstance(looking_at, ast.LocalTypedNameReference):
                continue
            looked_at_view = self._definition.get_view(looking_at.source_typed_name)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            looked_at_qualities[argument] = (
                looked_at_view.quality_assignment_block.as_set
            )
            self._record_view_use(
                argument,
                looking_at,
                looked_at_view,
                executed.get_view(argument.view.source_typed_name),
                operation_name,
                statement_diagnostics,
            )
        argument_diagnostics, literal_values = self._arguments_validator.validate(
            statement, looked_at_qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        return statement_diagnostics, literal_values

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
        statement_diagnostics, literal_values = self._analyze_execution(
            statement, executed
        )
        self._diagnostics.extend(statement_diagnostics)
        if not statement_diagnostics:
            self._analyze_valid_execution(statement, executed, literal_values)

    def _analyze_logical_operation_execution(
        self, statement: ast.LogicalOperationExecutionStatement
    ):
        view_arguments = _view_arguments(statement)
        executed = self._arguments_validator.get_executed_logical_operation(statement)
        if executed is None:
            self._mark_views_with_unknown_use(statement.arguments)
            return
        operation_name = statement.logical_operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        for argument, looking_at in view_arguments:
            looked_at_view = self._definition.get_view(looking_at.source_typed_name)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            logical_operation_view = executed.get_view(argument.view.source_typed_name)
            self._record_view_use(
                argument,
                looking_at,
                looked_at_view,
                logical_operation_view,
                operation_name,
                self._diagnostics,
            )
            if logical_operation_view is not None:
                self._check_logical_operation_support(
                    statement.logical_operation,
                    operation_name,
                    looking_at,
                    looked_at_view,
                    logical_operation_view,
                )
        _ = self._arguments_validator.validate_arguments(
            statement.logical_operation,
            statement.arguments,
            executed,
            operation_name,
            self._diagnostics,
        )

    def _mark_views_with_unknown_use(
        self, arguments: Sequence[ast.OperationArgumentStatement[ast.LookedAt]]
    ):
        """Mark the views the arguments look at as having unknown use, because the executed definition is missing."""
        for argument in arguments:
            looking_at = argument.looking_at
            if isinstance(looking_at, ast.LocalTypedNameReference):
                self._views_with_unknown_use.add(looking_at.source_typed_name)

    def _record_view_use(
        self,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        looking_at: ast.LocalTypedNameReference,
        looked_at_view: ast.InterfaceViewDefinition,
        executed_view: ast.ViewDefinition | None,
        operation_name: str,
        statement_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Record whether the executed view reads or writes the looked-at view, and report a use against its direction."""
        view_name = looked_at_view.typed_name.source_typed_name
        # An undefined view of the executed operation is reported when the
        # arguments are validated.
        if executed_view is None:
            self._views_with_unknown_use.add(view_name)
            return
        if executed_view.is_input:
            self._read_views.add(view_name)
            if not looked_at_view.is_input and view_name not in self._written_views:
                self._misused_views.add(view_name)
                statement_diagnostics.append(
                    diagnostics.ReadFromUnwrittenOutputViewDiagnostic(
                        location=looking_at.location,
                        looked_at_name=looking_at.source_typed_name,
                        view_name=argument.view.source_typed_name,
                        operation_name=operation_name,
                    )
                )
        if executed_view.is_output:
            self._written_views.add(view_name)
            if not looked_at_view.is_output:
                self._misused_views.add(view_name)
                statement_diagnostics.append(
                    diagnostics.WriteToInputOnlyViewDiagnostic(
                        location=looking_at.location,
                        looked_at_name=looking_at.source_typed_name,
                        view_name=argument.view.source_typed_name,
                        operation_name=operation_name,
                    )
                )

    def _check_logical_operation_support(
        self,
        logical_operation: ast.GlobalTypedNameReference,
        operation_name: str,
        looking_at: ast.LocalTypedNameReference,
        looked_at_view: ast.InterfaceViewDefinition,
        logical_operation_view: ast.LogicalOperationViewDefinition,
    ):
        """Check that the looked-at view's value quality supports the logical operation in each direction its view uses."""
        value_quality = looked_at_view.quality_assignment_block.value_quality
        # Structural validation reports views without a value quality.
        if value_quality is None:
            return
        value_result = self._definition_results.get(value_quality)
        # A missing value, or a definition of another type, was already
        # reported when its reference was resolved.
        if value_result is None:
            return
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
        if logical_operation_view.is_input and not may_be_read:
            self._diagnostics.append(
                diagnostics.LogicalOperationReadNotSupportedDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    logical_operation_name=operation_name,
                    value_name=value_name,
                )
            )
        if logical_operation_view.is_output and not may_be_written:
            self._diagnostics.append(
                diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
                    location=looking_at.location,
                    looked_at_name=looking_at.source_typed_name,
                    logical_operation_name=operation_name,
                    value_name=value_name,
                )
            )


def _view_arguments(
    statement: ast.LogicalOperationExecutionStatement,
) -> list[
    tuple[ast.OperationArgumentStatement[ast.LookedAt], ast.LocalTypedNameReference]
]:
    """Return each of the statement's arguments with the view it looks at."""
    view_arguments: list[
        tuple[ast.OperationArgumentStatement[ast.LookedAt], ast.LocalTypedNameReference]
    ] = []
    for argument in statement.arguments:
        looking_at = argument.looking_at
        if isinstance(looking_at, ast.Literal):
            raise NotImplementedError("Logical operations cannot look at literals yet.")
        view_arguments.append((argument, looking_at))
    return view_arguments


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
        self._fulfill_every_view_direction()

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
        self._fulfill_every_view_direction()
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
