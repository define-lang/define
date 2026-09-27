"""Reference graph validation of a value operation definition."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import literal_encoder
from define.compiler.validator.structural import name_validators

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict


class OperationDefinitionValidator:
    """Validates the Operation Execution Statements of a value operation against the operations they execute."""

    _definition: ast.OperationDefinition
    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _literal_encoder: literal_encoder.LiteralEncoder
    _diagnostics: list[diagnostics.Diagnostic]

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
        self._definition_results = definition_results
        self._literal_encoder = literal_encoder.LiteralEncoder(
            definition_results, self._enclosing_fqun
        )
        self._diagnostics = []

    @property
    def _enclosing_fqun(self) -> ast.Fqun:
        return self._definition.typed_name.name_content.fqun

    def analyze(self) -> validation_result.PostorderValidationResult:
        """Validate the definition and return its diagnostics."""
        for statement in self._definition.operation_statements:
            match statement:
                case ast.OperationExecutionStatement():
                    self._analyze_execution(statement)
                case ast.EncodingOperationExecutionStatement():
                    pass
        return validation_result.PostorderValidationResult(self._diagnostics)

    def _analyze_execution(self, statement: ast.OperationExecutionStatement):
        definition_result = self._definition_results.get(statement.operation)
        # A missing operation, or a definition of another type, was already
        # reported when its reference was resolved.
        if definition_result is None:
            return
        executed = typing.cast("ast.OperationDefinition", definition_result.definition)
        operation_name = statement.operation.source_form_in_universe(
            self._enclosing_fqun
        )
        if not executed.views:
            if statement.arguments:
                self._diagnostics.append(
                    diagnostics.ArgumentsForOperationWithoutViewsDiagnostic(
                        location=statement.arguments[0].location,
                        operation_name=operation_name,
                    )
                )
            return
        arguments = self._collect_arguments(statement, executed, operation_name)
        self._check_argument_order(arguments, executed, operation_name)
        self._check_missing_arguments(statement, arguments, executed, operation_name)

    def _collect_arguments(
        self,
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition,
        operation_name: str,
    ) -> dict[int, ast.OperationArgumentStatement]:
        """Check each argument that names an interface view of the executed operation, and return them by view index in source order."""
        arguments: dict[int, ast.OperationArgumentStatement] = {}
        for argument in statement.arguments:
            # Structural validation reports malformed view names.
            if name_validators.validate_local_name_format(argument.view.name_content):
                continue
            view_name = argument.view.source_typed_name
            index = executed.view_index(view_name)
            if index is None:
                self._diagnostics.append(
                    diagnostics.UndefinedOperationViewDiagnostic(
                        location=argument.view.location,
                        view_name=view_name,
                        operation_name=operation_name,
                        interface_view_names=[
                            view.typed_name.source_typed_name for view in executed.views
                        ],
                    )
                )
                continue
            # Structural validation reports a view given more than one argument.
            if index in arguments:
                continue
            arguments[index] = argument
            self._check_view_requirements(argument, executed.views[index])
        return arguments

    def _check_argument_order(
        self,
        arguments: dict[int, ast.OperationArgumentStatement],
        executed: ast.OperationDefinition,
        operation_name: str,
    ):
        latest_index = -1
        for index, argument in arguments.items():
            if index < latest_index:
                # Listing the whole order lets one diagnostic fix every
                # misplaced argument, instead of reporting each one relative to
                # another.
                self._diagnostics.append(
                    diagnostics.OperationArgumentOrderDiagnostic(
                        location=argument.view.location,
                        view_name=argument.view.source_typed_name,
                        operation_name=operation_name,
                        expected_order=[
                            executed.views[i].typed_name.source_typed_name
                            for i in sorted(arguments)
                        ],
                    )
                )
                return
            latest_index = index

    def _check_missing_arguments(
        self,
        statement: ast.OperationExecutionStatement,
        arguments: dict[int, ast.OperationArgumentStatement],
        executed: ast.OperationDefinition,
        operation_name: str,
    ):
        for view in executed.views:
            view_name = view.typed_name.source_typed_name
            # A duplicate view shares the first definition's argument.
            if executed.view_index(view_name) not in arguments:
                self._diagnostics.append(
                    diagnostics.MissingOperationArgumentDiagnostic(
                        location=statement.operation.location,
                        view_name=view_name,
                        operation_name=operation_name,
                    )
                )

    def _check_view_requirements(
        self,
        argument: ast.OperationArgumentStatement,
        executed_view: ast.ViewDefinition,
    ):
        """Check that the particle the argument looks at meets the executed view's constraints."""
        looking_at = argument.looking_at
        match looking_at:
            case ast.LocalTypedNameReference():
                looked_at_view = self._definition.get_view(looking_at.source_typed_name)
                # Structural validation reports undefined views.
                if looked_at_view is None:
                    return
                looked_at_name = looking_at.source_typed_name
                looked_at_kind = diagnostics.LookedAtKind.VIEW
                qualities = looked_at_view.constraints.as_set
            case ast.Literal():
                self._check_literal_translation(looking_at, executed_view)
                return
            case ast.PositionReference():
                # Structural validation reports views looking at positions
                # within a value operation.
                return
        missing: list[str] = []
        for requirement in executed_view.constraints.requirements:
            constraint = requirement.typed_global_name
            if constraint.full_typed_name not in qualities:
                missing.append(constraint.source_form_in_universe(self._enclosing_fqun))
        if missing:
            self._diagnostics.append(
                diagnostics.OperationArgumentViolatesConstraintsDiagnostic(
                    location=looking_at.location,
                    view_name=argument.view.source_typed_name,
                    looked_at_name=looked_at_name,
                    looked_at_kind=looked_at_kind,
                    missing_qualities=missing,
                )
            )

    def _check_literal_translation(
        self, literal: ast.Literal, executed_view: ast.ViewDefinition
    ):
        """Check that the literal can be translated into the executed view's value."""
        value_type = executed_view.constraints.value_constraint
        # Structural validation reports views without a value constraint.
        if value_type is None:
            return
        # The literal is translated into whatever the view requires, so it
        # always has the view's qualities; only that translation can fail.
        _, literal_diagnostics = self._literal_encoder.encode(literal, value_type)
        self._diagnostics.extend(literal_diagnostics)
