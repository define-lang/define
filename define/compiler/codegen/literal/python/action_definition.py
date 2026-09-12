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
    from define.compiler.validator import codegen_input


@final
class ActionDefinitionGenerator:
    """Generate an action's interface and serial run method."""

    def __init__(
        self,
        action_input: codegen_input.ActionCodegenInput,
        converter: naming.NameConverter,
        *,
        trace_operations: bool,
    ):
        """Initialize from validated definitions and known destructions."""
        self._action_input = action_input
        self._converter = converter
        self._statements = action_statements.ActionStatementsGenerator(
            action_input,
            converter,
            trace_operations=trace_operations,
        )
        self._trace_operations = trace_operations

    def generate(self) -> action_context.ActionDefinitionContext:
        """Build the template context for this action."""
        definition = self._action_input.definition
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
        generated = self._statements.generate()
        generated.imports.update(quality.module_name for quality in implied_qualities)
        for position in interfaces:
            generated.imports.update(
                quality.module_name for quality in position.constraints
            )
        propagated_destructions = self._action_input.propagated_destructions
        contract_names = self._converter.destruction_method_names(
            propagated_destructions
        ).values()
        contract_methods: list[str] = []
        for name in contract_names:
            contract_methods.append(naming.RUN_DESTRUCTORS_PREFIX + name)
            contract_methods.append(naming.DESTROY_PREFIX + name)
        return action_context.ActionDefinitionContext(
            class_name=self._converter.class_name(
                definition.typed_name.name_content.path.relative_path
            ),
            module_name=self._converter.module_name(definition.typed_name.name_content),
            statements=generated.statements,
            interface_positions=interfaces,
            implied_qualities=implied_qualities,
            imports=sorted(generated.imports),
            contract_class_name=(
                self._converter.destruction_contract_class_name(
                    definition.typed_name.name_content.path.relative_path
                )
                if contract_methods
                else None
            ),
            contract_methods=contract_methods,
            contract_definitions=generated.contract_definitions,
            trace_operations=self._trace_operations,
        )
