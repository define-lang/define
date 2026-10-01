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
    from collections.abc import Collection, Mapping

    from define.compiler.data_structures import typed_name_dict


class OperationDefinitionValidator[DefinitionT: ast.OperationDefinition](abc.ABC):
    """Validates the Operation Execution Statements of an operation definition against the operations they execute."""

    _definition: DefinitionT
    _diagnostics: list[diagnostics.Diagnostic]
    _arguments_validator: operation_arguments_validator.OperationArgumentsValidator
    _read_views: set[str]
    _written_views: set[str]
    # Views looked at by a view the executed operation does not define, so
    # whether they are read or written is unknown.
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
            if not isinstance(statement, ast.OperationExecutionStatement):
                self._analyze_encoding_or_computer_operation_execution(statement)
                continue
            executed = self._arguments_validator.get_executed_operation(statement)
            statement_diagnostics, literal_values = self._analyze_execution(
                statement, executed
            )
            self._diagnostics.extend(statement_diagnostics)
            if executed is not None and not statement_diagnostics:
                self._analyze_valid_execution(statement, executed, literal_values)
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
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement, codegen_input.EncodedLiteral
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
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition | None,
    ) -> tuple[
        list[diagnostics.Diagnostic],
        dict[ast.OperationArgumentStatement, codegen_input.EncodedLiteral],
    ]:
        """Validate an Operation Execution Statement, and return its diagnostics and its translated literals."""
        statement_diagnostics: list[diagnostics.Diagnostic] = []
        operation_name = statement.operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        looked_at_qualities: dict[ast.OperationArgumentStatement, Collection[str]] = {}
        for argument in statement.arguments:
            looking_at = argument.looking_at
            # Structural validation reports views looking at positions within an
            # operation definition.
            if not isinstance(looking_at, ast.LocalTypedNameReference):
                continue
            looked_at_view = self._definition.get_view(looking_at.source_typed_name)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            looked_at_qualities[argument] = looked_at_view.constraints.as_set
            view_name = looked_at_view.typed_name.source_typed_name
            interface_view = (
                None
                if executed is None
                else executed.get_view(argument.view.source_typed_name)
            )
            # A missing operation or an undefined interface view is reported
            # when the arguments are validated.
            if interface_view is None:
                self._views_with_unknown_use.add(view_name)
                continue
            if interface_view.is_input:
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
            if interface_view.is_output:
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
        argument_diagnostics, literal_values = self._arguments_validator.validate(
            statement, looked_at_qualities
        )
        statement_diagnostics.extend(argument_diagnostics)
        return statement_diagnostics, literal_values


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
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement, codegen_input.EncodedLiteral
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
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition,
        literal_values: Mapping[
            ast.OperationArgumentStatement, codegen_input.EncodedLiteral
        ],
    ):
        arguments = self._arguments_validator.operation_arguments(
            statement, executed, literal_values, ast.LocalTypedNameReference
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
