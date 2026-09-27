"""Reference graph validation of a value operation definition."""

from __future__ import annotations

import typing

from define.compiler import ast, diagnostics
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import (
    literal_encoder,
    operation_arguments_validator,
)

if typing.TYPE_CHECKING:
    from define.compiler.data_structures import typed_name_dict


class OperationDefinitionValidator:
    """Validates the Operation Execution Statements of a value operation against the operations they execute."""

    _definition: ast.OperationDefinition
    _diagnostics: list[diagnostics.Diagnostic]
    _arguments_validator: operation_arguments_validator.OperationArgumentsValidator

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
                case ast.EncodingOperationExecutionStatement():
                    pass
        return validation_result.PostorderValidationResult(self._diagnostics)

    def _analyze_execution(self, statement: ast.OperationExecutionStatement):
        looked_at_qualities: dict[ast.OperationArgumentStatement, frozenset[str]] = {}
        for argument in statement.arguments:
            looking_at = argument.looking_at
            # Structural validation reports views looking at positions within a
            # value operation.
            if not isinstance(looking_at, ast.LocalTypedNameReference):
                continue
            looked_at_view = self._definition.get_view(looking_at.source_typed_name)
            # Structural validation reports undefined views.
            if looked_at_view is None:
                continue
            looked_at_qualities[argument] = looked_at_view.constraints.as_set
        self._diagnostics.extend(
            self._arguments_validator.validate(statement, looked_at_qualities)
        )
