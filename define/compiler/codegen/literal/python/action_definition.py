"""Literal Python generation for action definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from define.compiler.codegen.literal.python import (
    action_statements,
    naming,
    renderer,
    value_types,
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

    def generate(self) -> renderer.ActionDefinition:
        """Build the template context for this action."""
        definition = self._action_input.definition
        interfaces: list[renderer.InterfacePosition] = []
        for position in definition.interface_positions:
            interfaces.append(
                renderer.InterfacePosition(
                    typed_name=position.typed_name.source_typed_name,
                    constraints=self._converter.constraints_to_class_references(
                        position.quality_assignment_block
                    ),
                    value_type=value_types.constrained_python_value_type(
                        position.quality_assignment_block
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
        module_name = self._converter.module_name(definition.typed_name.name_content)
        generated.imports.discard(module_name)
        contract_names = self._converter.destruction_method_names(
            self._action_input.destruction_contracts
        ).values()
        contract_methods: list[str] = []
        for name in contract_names:
            contract_methods.extend(
                (naming.RUN_DESTRUCTORS_PREFIX + name, naming.DESTROY_PREFIX + name)
            )
        return renderer.ActionDefinition(
            class_name=self._converter.class_name(definition.typed_name),
            module_name=module_name,
            statements=generated.statements,
            interface_positions=interfaces,
            implied_qualities=implied_qualities,
            imports=generated.imports,
            contract_class_name=(
                self._converter.destruction_contract_class_name(
                    definition.typed_name.name_content.path.relative_path
                )
                if contract_methods
                else None
            ),
            contract_methods=contract_methods,
            contract_definitions=generated.contract_definitions,
            guaranteed_particle_destructors=generated.guaranteed_particle_destructors,
            trace_operations=self._trace_operations,
        )
