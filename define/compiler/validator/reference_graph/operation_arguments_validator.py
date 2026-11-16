"""Validation of Operation Argument Statements against the views of the operations and logical operations they execute."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import abstract_program
from define.compiler.validator.structural import name_validators

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator import validation_result


class OperationArgumentsValidator:
    """Validates Operation Argument Statements against the views of the operations and logical operations they execute."""

    _definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ]
    _enclosing_fqun: ast.Fqun

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
        enclosing_fqun: ast.Fqun,
    ):
        """Initialize with the known definitions and the executing definition's FQUN."""
        self._definition_results = definition_results
        self._enclosing_fqun = enclosing_fqun

    def validate(
        self,
        statement: ast.OperationExecutionStatement[ast.LookedAt],
        looked_at_qualities: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], Collection[str]
        ],
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
        arguments = self.validate_arguments(
            statement.operation,
            statement.arguments,
            executed,
            operation_name,
            validation_diagnostics,
        )
        for index, argument in arguments.items():
            self._check_view_requirements(
                argument,
                executed.views[index],
                operation_name,
                looked_at_qualities,
                validation_diagnostics,
            )
        return validation_diagnostics

    def validate_arguments(
        self,
        executed_name: ast.GlobalTypedNameReference,
        arguments: Sequence[ast.OperationArgumentStatement[ast.LookedAt]],
        executed: ast.ExecutableDefinition[ast.ViewDefinition],
        operation_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> dict[int, ast.OperationArgumentStatement[ast.LookedAt]]:
        """Check that the arguments name each of the executed definition's views once, in order.

        Returns the arguments that name a view of the executed definition, by
        view index in source order.
        """
        view_indexes = executed.view_indexes_by_name()
        arguments_by_index = self._collect_arguments(
            arguments, executed, view_indexes, operation_name, validation_diagnostics
        )
        self._check_argument_order(
            arguments_by_index, executed, operation_name, validation_diagnostics
        )
        self._check_missing_arguments(
            executed_name,
            arguments_by_index,
            executed,
            view_indexes,
            operation_name,
            validation_diagnostics,
        )
        return arguments_by_index

    @staticmethod
    def value_operation_arguments[
        LookedAtT: (ast.PositionReference, ast.LocalTypedNameReference)
    ](
        statement: ast.OperationExecutionStatement[LookedAtT | ast.Literal],
        executed: ast.ValueOperationDefinition,
    ) -> list[abstract_program.Argument[LookedAtT]] | None:
        """Describe the arguments of a statement that executes a Value Operation, if each names one of its views."""
        arguments: list[abstract_program.Argument[LookedAtT]] = []
        view_indexes = executed.view_indexes_by_name()
        for argument in statement.arguments:
            view_index = view_indexes.get(argument.view.source_typed_name)
            # Structural validation reports a view name with an invalid format.
            if view_index is None:
                return None
            arguments.append(
                abstract_program.Argument(
                    interface_view=executed.views[view_index],
                    looking_at=argument.looking_at,
                )
            )
        return arguments

    def get_executed_operation(
        self,
        statement: ast.OperationExecutionStatement[ast.LookedAt],
    ) -> ast.OperationDefinition | None:
        """Return the operation the statement executes, if it is defined."""
        definition_result = self._definition_results.get(statement.operation)
        # A missing operation, or a definition of another type, was already
        # reported when its reference was resolved.
        if definition_result is None:
            return None
        return typing.cast("ast.OperationDefinition", definition_result.definition)

    def get_executed_logical_operation(
        self, statement: ast.LogicalOperationExecutionStatement
    ) -> ast.LogicalOperationDefinition | None:
        """Return the logical operation the statement executes, if it is defined."""
        definition_result = self._definition_results.get(statement.logical_operation)
        # A missing logical operation, or a definition of another type, was
        # already reported when its reference was resolved.
        if definition_result is None:
            return None
        return typing.cast(
            "ast.LogicalOperationDefinition", definition_result.definition
        )

    @staticmethod
    def _collect_arguments(
        arguments: Sequence[ast.OperationArgumentStatement[ast.LookedAt]],
        executed: ast.ExecutableDefinition[ast.ViewDefinition],
        view_indexes: Mapping[str, int],
        operation_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ) -> dict[int, ast.OperationArgumentStatement[ast.LookedAt]]:
        """Return the arguments that name a view of the executed definition, by view index in source order."""
        arguments_by_index: dict[int, ast.OperationArgumentStatement[ast.LookedAt]] = {}
        for argument in arguments:
            # Structural validation reports malformed view names.
            if name_validators.validate_local_name_format(argument.view.name_content):
                continue
            view_name = argument.view.source_typed_name
            index = view_indexes.get(view_name)
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
            if index in arguments_by_index:
                continue
            arguments_by_index[index] = argument
        return arguments_by_index

    @staticmethod
    def _check_argument_order(
        arguments: dict[int, ast.OperationArgumentStatement[ast.LookedAt]],
        executed: ast.ExecutableDefinition[ast.ViewDefinition],
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

    @staticmethod
    def _check_missing_arguments(
        executed_name: ast.GlobalTypedNameReference,
        arguments: dict[int, ast.OperationArgumentStatement[ast.LookedAt]],
        executed: ast.ExecutableDefinition[ast.ViewDefinition],
        view_indexes: Mapping[str, int],
        operation_name: str,
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        for view in executed.views:
            view_name = view.typed_name.source_typed_name
            # A duplicate view shares the first definition's argument.
            if view_indexes[view_name] not in arguments:
                validation_diagnostics.append(
                    diagnostics.MissingOperationArgumentDiagnostic(
                        location=executed_name.location,
                        view_name=view_name,
                        operation_name=operation_name,
                    )
                )

    def _check_view_requirements(
        self,
        argument: ast.OperationArgumentStatement[ast.LookedAt],
        interface_view: ast.InterfaceViewDefinition,
        operation_name: str,
        looked_at_qualities: Mapping[
            ast.OperationArgumentStatement[ast.LookedAt], Collection[str]
        ],
        validation_diagnostics: list[diagnostics.Diagnostic],
    ):
        """Check that the particle the argument looks at meets the quality assignments of the executed operation's interface view.

        A literal is translated into whatever its view requires, so it always
        has the view's qualities. Only that translation can fail, which is
        checked where the literal's encoding is known.
        """
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
        for statement in interface_view.quality_assignment_block.statements:
            quality = statement.typed_global_name
            # A missing quality was already reported when its reference was
            # resolved, and no particle could have it.
            if quality not in self._definition_results:
                continue
            if quality.full_typed_name not in qualities:
                missing.append(quality.source_form_in_universe(self._enclosing_fqun))
        if missing:
            validation_diagnostics.append(
                diagnostics.OperationArgumentMissingQualitiesDiagnostic(
                    location=looking_at.location,
                    view_name=argument.view.source_typed_name,
                    looked_at_name=looked_at_name,
                    looked_at_kind=looked_at_kind,
                    missing_qualities=missing,
                )
            )
