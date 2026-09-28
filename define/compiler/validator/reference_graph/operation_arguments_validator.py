"""Validation of Operation Argument Statements against the executed operation's interface views."""

from __future__ import annotations

import typing

from define.compiler import ast, built_in_definitions, diagnostics
from define.compiler.validator.structural import name_validators

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result
    from define.compiler.validator.reference_graph import literal_encoder


class OperationArgumentsValidator:
    """Validates Operation Argument Statements against the interface views of the operations they execute."""

    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _enclosing_fqun: ast.Fqun
    _literal_encoder: literal_encoder.LiteralEncoder

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        enclosing_fqun: ast.Fqun,
        literal_encoder: literal_encoder.LiteralEncoder,
    ):
        """Initialize with the known definitions, the executing definition's FQUN, and its literal encoder."""
        self._definition_results = definition_results
        self._enclosing_fqun = enclosing_fqun
        self._literal_encoder = literal_encoder

    def validate(
        self,
        statement: ast.OperationExecutionStatement,
        looked_at_qualities: Mapping[ast.OperationArgumentStatement, frozenset[str]],
    ) -> list[diagnostics.Diagnostic]:
        """Validate the statement's arguments against the executed operation's interface views.

        looked_at_qualities maps each argument that looks at a position or view
        to the full typed names of the qualities of the particle it looks at.
        Arguments without an entry are not checked against the views looking
        at them.
        """
        validation_diagnostics: list[diagnostics.Diagnostic] = []
        executed = self.get_executed_operation(statement)
        if executed is None:
            return validation_diagnostics
        operation_name = statement.operation.source_form_in_universe(
            self._enclosing_fqun
        )
        if not executed.views:
            if statement.arguments:
                validation_diagnostics.append(
                    diagnostics.ArgumentsForOperationWithoutViewsDiagnostic(
                        location=statement.arguments[0].location,
                        operation_name=operation_name,
                    )
                )
            return validation_diagnostics
        arguments = self._collect_arguments(
            statement, executed, operation_name, validation_diagnostics
        )
        self._check_argument_order(
            arguments, executed, operation_name, validation_diagnostics
        )
        self._check_missing_arguments(
            statement, arguments, executed, operation_name, validation_diagnostics
        )
        for index, argument in arguments.items():
            self._check_view_requirements(
                argument,
                executed,
                executed.views[index],
                operation_name,
                looked_at_qualities,
                validation_diagnostics,
            )
        return validation_diagnostics

    def get_executed_operation(
        self, statement: ast.OperationExecutionStatement
    ) -> ast.OperationDefinition | None:
        """Return the operation the statement executes, if it is defined."""
        # TODO: Remove this special case once the Define Standard Library
        # defines the built-in names.
        built_in_operation = built_in_definitions.get_operation(
            statement.operation.full_typed_name
        )
        if built_in_operation is not None:
            return built_in_operation
        definition_result = self._definition_results.get(statement.operation)
        # A missing operation, or a definition of another type, was already
        # reported when its reference was resolved.
        if definition_result is None:
            return None
        return typing.cast("ast.OperationDefinition", definition_result.definition)

    def _collect_arguments(
        self,
        statement: ast.OperationExecutionStatement,
        executed: ast.OperationDefinition,
        operation_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> dict[int, ast.OperationArgumentStatement]:
        """Return the arguments that name an interface view of the executed operation, by view index in source order."""
        arguments: dict[int, ast.OperationArgumentStatement] = {}
        for argument in statement.arguments:
            # Structural validation reports malformed view names.
            if name_validators.validate_local_name_format(argument.view.name_content):
                continue
            view_name = argument.view.source_typed_name
            index = executed.view_index(view_name)
            if index is None:
                validation_diagnostics.append(
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
        return arguments

    def _check_argument_order(
        self,
        arguments: dict[int, ast.OperationArgumentStatement],
        executed: ast.OperationDefinition,
        operation_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        latest_index = -1
        for index, argument in arguments.items():
            if index < latest_index:
                # Listing the whole order lets one diagnostic fix every
                # misplaced argument, instead of reporting each one relative to
                # another.
                validation_diagnostics.append(
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
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        for view in executed.views:
            view_name = view.typed_name.source_typed_name
            # A duplicate view shares the first definition's argument.
            if executed.view_index(view_name) not in arguments:
                validation_diagnostics.append(
                    diagnostics.MissingOperationArgumentDiagnostic(
                        location=statement.operation.location,
                        view_name=view_name,
                        operation_name=operation_name,
                    )
                )

    def _check_view_requirements(
        self,
        argument: ast.OperationArgumentStatement,
        executed: ast.OperationDefinition,
        interface_view: ast.ViewDefinition,
        operation_name: str,
        looked_at_qualities: Mapping[ast.OperationArgumentStatement, frozenset[str]],
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Check that the particle the argument looks at meets the constraints of the executed operation's interface view."""
        looking_at = argument.looking_at
        match looking_at:
            case ast.Literal():
                if interface_view.is_output:
                    validation_diagnostics.append(
                        diagnostics.OutputViewLooksAtLiteralDiagnostic(
                            location=looking_at.location,
                            view_name=argument.view.source_typed_name,
                            operation_name=operation_name,
                        )
                    )
                    return
                self._check_literal_translation(
                    looking_at, executed, interface_view, validation_diagnostics
                )
                return
            case ast.LocalTypedNameReference():
                looked_at_name = looking_at.source_typed_name
                looked_at_kind = diagnostics.LookedAtKind.VIEW
            case ast.PositionReference():
                looked_at_name = looking_at.source_chained_name
                looked_at_kind = diagnostics.LookedAtKind.POSITION
        qualities = looked_at_qualities.get(argument)
        if qualities is None:
            return
        missing: list[str] = []
        for requirement in interface_view.constraints.requirements:
            constraint = requirement.typed_global_name
            if constraint.full_typed_name not in qualities:
                missing.append(constraint.source_form_in_universe(self._enclosing_fqun))
        if missing:
            validation_diagnostics.append(
                diagnostics.OperationArgumentViolatesConstraintsDiagnostic(
                    location=looking_at.location,
                    view_name=argument.view.source_typed_name,
                    looked_at_name=looked_at_name,
                    looked_at_kind=looked_at_kind,
                    missing_qualities=missing,
                )
            )

    def _check_literal_translation(
        self,
        literal: ast.Literal,
        executed: ast.OperationDefinition,
        interface_view: ast.ViewDefinition,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Check that the literal can be translated into what the executed operation's interface view requires."""
        # The literal is translated into whatever the view requires, so it
        # always has the view's qualities; only that translation can fail.
        if isinstance(executed, ast.EncodingOperationDefinition):
            for requirement in interface_view.constraints.requirements:
                constraint = requirement.typed_global_name
                if constraint.name_type == ast.NameType.ENCODING:
                    validation_diagnostics.extend(
                        self._literal_encoder.encode_in_encoding(literal, constraint)
                    )
            return
        value_type = interface_view.constraints.value_constraint
        # Structural validation reports views without a value constraint.
        if value_type is None:
            return
        _, literal_diagnostics = self._literal_encoder.encode(literal, value_type)
        validation_diagnostics.extend(literal_diagnostics)
