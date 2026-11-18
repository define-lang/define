"""Validation of an Encoding Operation definition, and collection of its steps for code generation."""

from __future__ import annotations

import typing
from typing import override

from define.compiler import ast, name_types
from define.compiler.association_resolution import (
    concrete_program,
    literal_encoder,
)
from define.compiler.validator import validation_result
from define.compiler.validator.reference_graph import operation_definition_validator

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


class EncodingOperationDefinitionValidator(
    operation_definition_validator.OperationDefinitionValidator[
        ast.EncodingOperationDefinition,
        validation_result.EncodingOperationPostorderValidationResult,
    ]
):
    """Validates an Encoding Operation definition and collects its steps for code generation."""

    _literal_encoder: literal_encoder.LiteralEncoder
    _steps: list[concrete_program.OperationStep]
    _computer_operation: ast.ComputerOperationExecutionStatement | None

    def __init__(
        self,
        definition: ast.EncodingOperationDefinition,
        definitions: Mapping[str, ast.GlobalDefinition],
    ):
        """Initialize with the Encoding Operation Definition and known definitions."""
        super().__init__(definition, definitions)
        self._literal_encoder = literal_encoder.LiteralEncoder(definitions)
        self._steps = []
        self._computer_operation = None

    @override
    def analyze(self) -> validation_result.EncodingOperationPostorderValidationResult:
        # The parser allows `execute the computer operation.` only as the one
        # statement of an Encoding Operation. It reads and writes every
        # interface view, so there are no view uses to check.
        match self._definition.operation_statements.statements:
            case [ast.ComputerOperationExecutionStatement() as statement]:
                # TODO: Once users can define Encoding Operations that
                # associate with Value Operations, report a computer operation
                # that the compiler cannot perform. Code generation relies on
                # performing every one.
                self._computer_operation = statement
                return self._build_result()
            case _:
                return super().analyze()

    @override
    def _analyze_valid_execution(
        self,
        statement: ast.OperationExecutionStatement[
            ast.LocalTypedNameReference | ast.Literal
        ],
        executed: ast.OperationDefinition,
    ):
        # The grammar allows an Encoding Operation to execute only Encoding
        # Operations.
        encoding_operation = typing.cast("ast.EncodingOperationDefinition", executed)
        arguments: list[
            concrete_program.OperationArgument[ast.LocalTypedNameReference]
        ] = []
        is_complete = True
        for argument in statement.arguments:
            interface_view = encoding_operation.get_view(
                argument.view.source_typed_name
            )
            # Structural validation reports a view name with an invalid format.
            if interface_view is None:
                return
            looking_at = argument.looking_at
            if not isinstance(looking_at, ast.Literal):
                arguments.append(
                    concrete_program.OperationArgument(
                        interface_view=interface_view, looking_at=looking_at
                    )
                )
                continue
            value = self._translate_literal(looking_at, interface_view)
            # Every literal is translated, so each one that cannot be is
            # reported.
            if value is None:
                is_complete = False
                continue
            arguments.append(
                concrete_program.OperationArgument(
                    interface_view=interface_view, looking_at=value
                )
            )
        if is_complete:
            self._steps.append(
                concrete_program.OperationExecution(
                    runtime_operation=statement.operation, arguments=arguments
                )
            )

    def _translate_literal(
        self, literal: ast.Literal, interface_view: ast.InterfaceViewDefinition
    ) -> concrete_program.EncodedLiteral | None:
        """Return the literal translated into the encoding of the interface view of an executed Encoding Operation, if it can be translated."""
        translated: concrete_program.EncodedLiteral | None = None
        for assignment in interface_view.quality_assignment_block.statements:
            encoding = assignment.typed_global_name
            if encoding.name_type == name_types.NameType.ENCODING:
                value, literal_diagnostics = self._literal_encoder.encode_in_encoding(
                    literal, encoding, self._definition.typed_name.name_content.fqun
                )
                self._diagnostics.extend(literal_diagnostics)
                # Generated code represents a value the same way in every
                # encoding, so any one translation serves.
                if translated is None:
                    translated = value
        return translated

    @override
    def _add_local_statement(
        self, statement: ast.LocalViewDefinition | ast.ViewSettingStatement
    ):
        self._steps.append(statement)

    @override
    def _build_result(
        self,
    ) -> validation_result.EncodingOperationPostorderValidationResult:
        return validation_result.EncodingOperationPostorderValidationResult(
            diagnostics=self._diagnostics,
            encoding_operation=concrete_program.ConcreteEncodingOperation(
                definition=self._definition,
                body=self._computer_operation or self._steps,
            ),
        )
