"""Resolve the abstract program that reference graph validation produces to concrete code, through the program's associations."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.association_resolution import (
    associated_encoding_operation_checks,
    associations,
    concrete_program,
    encoding_operation_definition_validator,
    literal_encoder,
    value_operation_resolver,
)
from define.compiler.errors import diagnostics
from define.compiler.validator.reference_graph import abstract_program

if typing.TYPE_CHECKING:
    from collections.abc import Collection

    from define.compiler.data_structures import typed_name_dict
    from define.compiler.graphs import reference_graph, reference_graph_order
    from define.compiler.validator import validation_result


@typing.final
class AssociationResolver:
    """Resolves each definition of the abstract program to concrete code, after reference graph validation validates it.

    Definitions are resolved concurrently, in reference graph order, so a
    definition is resolved only after everything it references.
    """

    def __init__(
        self,
        definition_results: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
            validation_result.DefinitionValidationResult,
        ],
    ):
        """Initialize with the known definitions."""
        self._definition_results = definition_results
        self._associations = associations.Associations(definition_results)
        self._literal_encoder = literal_encoder.LiteralEncoder(definition_results)
        self._value_operations = value_operation_resolver.ValueOperationResolver(
            self._associations, self._literal_encoder
        )
        self._actions: dict[str, concrete_program.ConcreteAction] = {}
        self._encoding_operations: dict[
            str, concrete_program.ConcreteEncodingOperation
        ] = {}

    def resolve_value(
        self, definition: ast.ValueDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Find the one encoding associated with a value quality, and return a diagnostic if it has none."""
        return self._associations.add_value(definition)

    def resolve_logical_operation(
        self, definition: ast.LogicalOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Add a logical operation's associations with Encoding Operations, and return the diagnostics about them."""
        return self._associations.add_logical_operation(definition)

    def resolve_value_operation(
        self,
        definition: ast.ValueOperationDefinition,
        steps: Collection[abstract_program.ValueOperationStep],
    ) -> list[diagnostics.Diagnostic]:
        """Encode the literals in the steps of a valid Value Operation, and return the diagnostics about the ones that cannot be encoded."""
        return self._value_operations.add_value_operation(definition, steps)

    def resolve_action(
        self, action: abstract_program.AbstractAction
    ) -> list[diagnostics.Diagnostic]:
        """Encode the action's literals and choose what each of its executions of a Value Operation runs, and return the diagnostics about them."""
        definition = action.definition
        action_diagnostics: list[diagnostics.Diagnostic] = []
        steps: list[concrete_program.ActionStep] = []
        for step in action.steps:
            match step:
                case abstract_program.LiteralValueSetting():
                    value_setting, value_setting_diagnostics = (
                        self._literal_value_setting(definition, step)
                    )
                    action_diagnostics.extend(value_setting_diagnostics)
                    if value_setting is not None:
                        steps.append(value_setting)
                case abstract_program.ActionOperationExecution():
                    execution, execution_diagnostics = self._action_operation_execution(
                        definition, step
                    )
                    action_diagnostics.extend(execution_diagnostics)
                    if execution is not None:
                        steps.append(execution)
                case _:
                    steps.append(step)
        self._actions[definition.typed_name.full_typed_name] = (
            concrete_program.ConcreteAction(
                definition=definition,
                steps=steps,
                destruction_contracts=action.destruction_contracts,
                guaranteed_particle_destructors=action.guaranteed_particle_destructors,
            )
        )
        return action_diagnostics

    def chosen_edges(self) -> list[reference_graph.ReferenceEdge]:
        """Return the edge to each encoding and Encoding Operation that resolution chose, once every definition is resolved."""
        return self._associations.chosen_edges()

    def resolve_encoding_operations(self):
        """Validate each loaded Encoding Operation and check each chosen association against the Encoding Operation it names, once the chosen ones are loaded, and add the diagnostics to the definitions they are about."""
        for definition_result in self._definition_results.values():
            definition = definition_result.definition
            if isinstance(definition, ast.EncodingOperationDefinition):
                definition_result.diagnostics.extend(
                    self._resolve_encoding_operation(definition)
                )
        for chosen in self._associations.chosen_encoding_operations():
            logical_operation = chosen.logical_operation
            self._definition_results[logical_operation.typed_name].diagnostics.extend(
                associated_encoding_operation_checks.check(
                    logical_operation,
                    self._definition_results,
                    [chosen.encoding_operation_association],
                )
            )

    def _resolve_encoding_operation(
        self, definition: ast.EncodingOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Validate an Encoding Operation, add it to the concrete program, and return the diagnostics about it."""
        result = encoding_operation_definition_validator.EncodingOperationDefinitionValidator(
            definition, self._definition_results
        ).analyze()
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            result.encoding_operation
        )
        return result.diagnostics

    def concrete_program(
        self, definition_order: reference_graph_order.ReferenceGraphOrder
    ) -> concrete_program.ConcreteProgram:
        """Return the concrete program, once every definition is resolved."""
        return concrete_program.ConcreteProgram(
            definition_order=definition_order,
            actions=self._actions,
            encoding_operations=self._encoding_operations,
            value_encodings=self._associations.value_encodings(),
            composite_value_operations=self._value_operations.composite_value_operations(),
        )

    def _literal_value_setting(
        self,
        action: ast.ActionDefinition,
        value_setting: abstract_program.LiteralValueSetting,
    ) -> tuple[
        concrete_program.LiteralValueSetting | None, list[diagnostics.Diagnostic]
    ]:
        value_encoding = self._associations.value_encoding(value_setting.value_quality)
        # A value quality without an encoding was already reported at its
        # definition.
        if value_encoding is None:
            return None, []
        value, literal_diagnostics = self._literal_encoder.encode(
            value_setting.literal,
            value_setting.value_quality,
            value_encoding,
            action.typed_name.name_content.fqun,
        )
        if value is None:
            return None, literal_diagnostics
        return concrete_program.LiteralValueSetting(
            target_position=value_setting.target_position,
            value_quality=value_setting.value_quality,
            value=value,
        ), literal_diagnostics

    def _action_operation_execution(
        self,
        action: ast.ActionDefinition,
        execution: abstract_program.ActionOperationExecution,
    ) -> tuple[
        concrete_program.ActionOperationExecution | None, list[diagnostics.Diagnostic]
    ]:
        """Return what an Operation Execution Statement in the action runs for the encodings of what its arguments look at, if it can run, and the diagnostics explaining why not."""
        arguments, argument_diagnostics = self._value_operations.resolve_arguments(
            execution.arguments, action.typed_name.name_content.fqun
        )
        if arguments is None:
            return None, argument_diagnostics
        view_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for argument in arguments:
            looking_at = argument.looking_at
            view_name = argument.interface_view.typed_name.source_typed_name
            if isinstance(looking_at, concrete_program.EncodedLiteral):
                view_encodings[view_name] = looking_at.encoding
                continue
            value_quality = execution.looked_at_value_qualities.get(view_name)
            # A looked-at position whose value quality is unknown was already
            # reported.
            if value_quality is None:
                return None, argument_diagnostics
            encoding = self._associations.value_encoding(value_quality)
            # A value quality without an encoding was already reported at its
            # definition.
            if encoding is None:
                return None, argument_diagnostics
            view_encodings[view_name] = encoding
        result = self._value_operations.resolve(
            execution.value_operation, view_encodings
        )
        if isinstance(result, value_operation_resolver.MissingEncodingOperation):
            return None, [
                *argument_diagnostics,
                _missing_encoding_operation_diagnostic(action, execution, result),
            ]
        if result is None:
            return None, argument_diagnostics
        return concrete_program.ActionOperationExecution(
            operation=execution.operation,
            operation_arguments=arguments,
            runtime_operation=result.runtime_operation,
            arguments=result.arguments_for(arguments),
        ), argument_diagnostics


def _missing_encoding_operation_diagnostic(
    action: ast.ActionDefinition,
    execution: abstract_program.ActionOperationExecution,
    missing: value_operation_resolver.MissingEncodingOperation,
) -> diagnostics.MissingEncodingOperationDiagnostic:
    enclosing_fqun = action.typed_name.name_content.fqun
    # The encoding of each of the logical operation's views as it would be
    # written in the action's universe.
    view_encodings: dict[str, str] = {}
    for view, encoding in missing.view_encodings.items():
        view_encodings[view] = encoding.source_form_in_universe(enclosing_fqun)
    # The executions from the action down to the Logical Operation Execution
    # Statement, in the order they happen. Each execution is in the operation
    # that the one before it executes.
    stack: list[diagnostics.OperationExecutionStep] = []
    executing_name = action.typed_name.source_typed_name
    for executed in (execution.operation, *missing.execution_stack):
        executed_name = executed.source_form_in_universe(enclosing_fqun)
        stack.append(
            diagnostics.OperationExecutionStep(
                executing_name=executing_name,
                executed_name=executed_name,
                location=executed.location,
            )
        )
        executing_name = executed_name
    return diagnostics.MissingEncodingOperationDiagnostic(
        location=execution.operation.location,
        logical_operation_name=missing.logical_operation.source_form_in_universe(
            enclosing_fqun
        ),
        view_encodings=view_encodings,
        execution_stack=stack,
    )
