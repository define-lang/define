"""Literal Python generation for action definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler.codegen.literal.python import (
    action_context,
    action_statements,
    naming,
    template_context,
)

if TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.validator.reference_graph import (
        action_contract,
    )


@final
class ActionDefinitionGenerator:
    """Generate an action's interface and serial run method."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        destructions: dict[ast.SourceLocation, list[ast.PositionReference]],
        triggered_actions: action_contract.TriggeredActions,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated definitions and known destructions."""
        self._definition = definition
        self._converter = converter
        self._statements = action_statements.ActionStatementsGenerator(
            definition,
            converter,
            destructions,
            triggered_actions,
            trace_operations=trace_operations,
        )
        self._trace_operations = trace_operations

    def generate(self) -> action_context.ActionDefinitionContext:
        """Build the template context for this action."""
        definition = self._definition
        interfaces: list[template_context.InterfacePositionContext] = []
        for position in definition.interface_positions:
            interfaces.append(
                template_context.InterfacePositionContext(
                    typed_name=position.typed_name.source_typed_name,
                    constraints=self._converter.constraints_to_class_references(
                        position.constraints
                    ),
                )
            )
        implied_qualities = self._converter.implied_qualities_to_class_references(
            definition.quality_implications
        )
        statements, imports = self._statements.generate()
        imports.update(quality.module_name for quality in implied_qualities)
        for position in interfaces:
            imports.update(quality.module_name for quality in position.constraints)
        return action_context.ActionDefinitionContext(
            class_name=self._converter.class_name(
                definition.typed_name.name_content.path.relative_path
            ),
            module_name=self._converter.module_name(definition.typed_name.name_content),
            statements=statements,
            interface_positions=interfaces,
            implied_qualities=implied_qualities,
            imports=sorted(imports),
            trace_operations=self._trace_operations,
        )
