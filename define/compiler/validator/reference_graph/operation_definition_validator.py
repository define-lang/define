"""Reference graph validation of a Value Operation or Encoding Operation definition."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import (
    literal_encoder,
    operation_arguments_validator,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict


class OperationDefinitionValidator:
    """Validates the Operation Execution Statements of an operation definition against the operations they execute."""

    _definition: ast.OperationDefinition
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
        definition: ast.OperationDefinition,
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
        """Validate the definition and return its diagnostics."""
        for statement in self._definition.operation_statements:
            match statement:
                case ast.OperationExecutionStatement():
                    self._analyze_execution(statement)
                case (
                    ast.EncodingOperationExecutionStatement()
                    | ast.ComputerOperationExecutionStatement()
                ):
                    self._analyze_encoding_or_computer_operation_execution()
        self._check_view_directions_fulfilled()
        return validation_result.PostorderValidationResult(self._diagnostics)

    def _analyze_encoding_or_computer_operation_execution(self):
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

    def _analyze_execution(self, statement: ast.OperationExecutionStatement):
        executed = self._arguments_validator.get_executed_operation(statement)
        operation_name = statement.operation.source_form_in_universe(
            self._definition.typed_name.name_content.fqun
        )
        looked_at_qualities: dict[ast.OperationArgumentStatement, frozenset[str]] = {}
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
                    self._diagnostics.append(
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
                    self._diagnostics.append(
                        diagnostics.WriteToInputOnlyViewDiagnostic(
                            location=looking_at.location,
                            looked_at_name=looking_at.source_typed_name,
                            view_name=argument.view.source_typed_name,
                            operation_name=operation_name,
                        )
                    )
        self._diagnostics.extend(
            self._arguments_validator.validate(statement, looked_at_qualities)
        )
