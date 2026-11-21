"""Resolve the abstract program that reference graph validation produces to concrete code, through the program's associations."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.association_resolution import (
    abstract_operation_associations,
    associated_encoding_operation_checks,
    concrete_program,
    encoding_operation_definition_validator,
    literal_encoder,
    value_operation_resolver,
    value_quality_associations,
)
from define.compiler.errors import association_resolution_diagnostics
from define.compiler.validator.reference_graph import abstract_program

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from define.compiler.config import config_loader, project_roots
    from define.compiler.data_structures import define_path
    from define.compiler.errors import config_diagnostics, diagnostics
    from define.compiler.graphs import reference_graph, reference_graph_order


@typing.final
class AssociationResolver:
    """Resolves each definition of the abstract program to concrete code, after reference graph validation validates it.

    Definitions are resolved concurrently, in reference graph order, so a
    definition is resolved only after everything it references.
    """

    def __init__(
        self,
        definitions: Mapping[str, ast.GlobalDefinition],
        roots: project_roots.ProjectRoots,
    ):
        """Initialize with the program's definitions by full typed name, and the program's project roots, whose configs have the associations."""
        self._definitions = definitions
        self._project_roots = roots
        self._abstract_operation_associations = (
            abstract_operation_associations.AbstractOperationAssociations(roots)
        )
        self._value_quality_associations = (
            value_quality_associations.ValueQualityAssociations(definitions, roots)
        )
        self._literal_encoder = literal_encoder.LiteralEncoder(definitions)
        self._value_operations = value_operation_resolver.ValueOperationResolver(
            self._abstract_operation_associations,
            self._value_quality_associations,
            self._literal_encoder,
        )
        self._actions: dict[str, concrete_program.ConcreteAction] = {}
        self._encoding_operations: dict[
            str, concrete_program.ConcreteEncodingOperation
        ] = {}

    def resolve(
        self,
        definition: abstract_program.AbstractDefinition | ast.PositionDefinition,
    ) -> list[diagnostics.Diagnostic]:
        """Resolve a definition once it is validated and everything it references is resolved, and return the diagnostics about it."""
        match definition:
            case abstract_program.AbstractAction():
                return self.resolve_action(definition)
            case abstract_program.AbstractValueOperation():
                self._value_operations.add_value_operation(
                    definition.definition, definition.steps
                )
                return []
            case ast.LogicalOperationDefinition():
                return self.resolve_logical_operation(definition)
            case ast.PositionDefinition():
                self._look_up_value_encoding(definition.quality_assignment_block)
                return []
            # A value quality's encoding is looked up when something needs it.
            case ast.ValueDefinition():
                return []

    def _look_up_value_encoding(
        self, quality_assignment_block: ast.QualityAssignmentBlock | None
    ):
        """Look up the encoding of the value quality that a position's quality assignments assign, if they assign one, because code generation represents the position's values in that encoding."""
        if (
            quality_assignment_block is not None
            and quality_assignment_block.value_quality is not None
        ):
            _ = self._value_quality_associations.value_encoding(
                quality_assignment_block.value_quality
            )

    def resolve_logical_operation(
        self, definition: ast.LogicalOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Add a logical operation's associations with Encoding Operations, and return the diagnostics about them."""
        return self._abstract_operation_associations.add_logical_operation(definition)

    def resolve_action(
        self, action: abstract_program.AbstractAction
    ) -> list[diagnostics.Diagnostic]:
        """Encode the action's literals and choose what each of its executions of a Value Operation runs, and return the diagnostics about them."""
        definition = action.definition
        for position in definition.interface_positions:
            self._look_up_value_encoding(position.quality_assignment_block)
        action_diagnostics: list[diagnostics.Diagnostic] = []
        steps: list[concrete_program.ActionStep] = []
        for step in action.steps:
            match step:
                case ast.LocalPositionDefinition():
                    self._look_up_value_encoding(step.quality_assignment_block)
                    steps.append(step)
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

    def chosen_edges(
        self,
    ) -> tuple[list[reference_graph.ReferenceEdge], Collection[diagnostics.Diagnostic]]:
        """Return the edge to each encoding and Encoding Operation that resolution chose, once every definition is resolved, with the diagnostics about the edges.

        An edge to a universe that the project whose config writes the edge
        does not configure is left out. Each such universe is reported once
        for each config file, at the place in the file that names it first.
        """
        candidates = [
            *self._value_quality_associations.encoding_edges(),
            *self._abstract_operation_associations.chosen_edges(),
        ]
        edges: list[reference_graph.ReferenceEdge] = []
        # The diagnostic for each config file and the universe that it names.
        unconfigured: dict[
            tuple[str | None, str],
            config_diagnostics.ExternalUniverseNotConfiguredDiagnostic,
        ] = {}
        for edge in candidates:
            reference = edge.global_name_reference
            # An association is in the config of the project whose universe
            # its references are written in, which is loaded.
            _, root_config = typing.cast(
                "tuple[define_path.DefinePath, config_loader.Config]",
                self._project_roots.get_loaded_root_config(
                    reference.enclosing_fqun.canonical
                ),
            )
            diagnostic = root_config.check_universe_configured(reference.name_content)
            if diagnostic is None:
                edges.append(edge)
                continue
            location = diagnostic.location
            key = (location.file_path, diagnostic.universe)
            first = unconfigured.get(key)
            # Resolution chooses associations concurrently, so the edges come
            # in no fixed order.
            if first is None or (location.line, location.column) < (
                first.location.line,
                first.location.column,
            ):
                unconfigured[key] = diagnostic
        return edges, unconfigured.values()

    def lookup_diagnostic_lists(self) -> list[list[diagnostics.Diagnostic]]:
        """Return the diagnostics that resolution found when something first needed an encoding, a Value Operation's associations, or a Value Operation's literals, once every definition is resolved."""
        return [
            self._value_quality_associations.diagnostics(),
            self._abstract_operation_associations.value_operation_diagnostics(),
            self._value_operations.literal_diagnostics(),
        ]

    def resolve_encoding_operations(
        self, encoding_operations: Iterable[ast.EncodingOperationDefinition]
    ) -> list[diagnostics.Diagnostic]:
        """Validate each loaded Encoding Operation and check each chosen association against the Encoding Operation it names, once the chosen ones are loaded, and return the diagnostics."""
        found: list[diagnostics.Diagnostic] = []
        for definition in encoding_operations:
            found.extend(self._resolve_encoding_operation(definition))
        for (
            chosen
        ) in self._abstract_operation_associations.chosen_encoding_operations():
            found.extend(
                associated_encoding_operation_checks.check(
                    chosen.abstract_operation,
                    self._definitions,
                    [chosen.encoding_operation_association],
                )
            )
        return found

    def _resolve_encoding_operation(
        self, definition: ast.EncodingOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Validate an Encoding Operation, add it to the concrete program, and return the diagnostics about it."""
        result = encoding_operation_definition_validator.EncodingOperationDefinitionValidator(
            definition, self._definitions
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
            value_encodings=self._value_quality_associations.value_encodings(),
            composite_value_operations=self._value_operations.composite_value_operations(),
        )

    def _literal_value_setting(
        self,
        action: ast.ActionDefinition,
        value_setting: abstract_program.LiteralValueSetting,
    ) -> tuple[
        concrete_program.LiteralValueSetting | None, list[diagnostics.Diagnostic]
    ]:
        value_encoding = self._value_quality_associations.value_encoding(
            value_setting.value_quality
        )
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
            encoding = self._value_quality_associations.value_encoding(value_quality)
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
        if isinstance(result, concrete_program.OperationExecution):
            return concrete_program.ActionOperationExecution(
                operation=execution.operation,
                operation_arguments=arguments,
                runtime_operation=result.runtime_operation,
                arguments=result.arguments_for(arguments),
            ), argument_diagnostics
        return concrete_program.ActionOperationExecution(
            operation=execution.operation,
            operation_arguments=arguments,
            runtime_operation=result,
            arguments=arguments,
        ), argument_diagnostics


def _missing_encoding_operation_diagnostic(
    action: ast.ActionDefinition,
    execution: abstract_program.ActionOperationExecution,
    missing: value_operation_resolver.MissingEncodingOperation,
) -> association_resolution_diagnostics.MissingEncodingOperationDiagnostic:
    enclosing_fqun = action.typed_name.name_content.fqun
    # The encoding of each of the logical operation's views as it would be
    # written in the action's universe.
    view_encodings: dict[str, str] = {}
    for view, encoding in missing.view_encodings.items():
        view_encodings[view] = encoding.source_form_in_universe(enclosing_fqun)
    # The executions from the action down to the Logical Operation Execution
    # Statement, in the order they happen. Each execution is in the operation
    # that the one before it executes.
    stack: list[association_resolution_diagnostics.OperationExecutionStep] = []
    executing_name = action.typed_name.source_typed_name
    for executed in (execution.operation, *missing.execution_stack):
        executed_name = executed.source_form_in_universe(enclosing_fqun)
        stack.append(
            association_resolution_diagnostics.OperationExecutionStep(
                executing_name=executing_name,
                executed_name=executed_name,
                location=executed.location,
            )
        )
        executing_name = executed_name
    return association_resolution_diagnostics.MissingEncodingOperationDiagnostic(
        location=execution.operation.location,
        logical_operation_name=missing.logical_operation.source_form_in_universe(
            enclosing_fqun
        ),
        view_encodings=view_encodings,
        execution_stack=stack,
    )
