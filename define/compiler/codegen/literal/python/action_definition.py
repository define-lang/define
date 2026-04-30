"""Python code generator for action definitions."""

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
    naming,
    template_context,
)


class ActionDefinitionGenerator:
    """Extracts template context from an action definition."""

    _converter: naming.NameConverter
    _definition: ast.ActionDefinition

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
    ):
        """Initialize with the action definition to extract data from."""
        self._definition = definition
        self._converter = converter

    def generate(self) -> template_context.ActionDefinitionContext:
        """Generate template context for the action definition."""
        name_content = self._definition.typed_name.name_content
        class_name = self._converter.class_name(name_content.path.relative_path)
        module_name = self._converter.module_name(name_content)

        interface_positions = [
            template_context.InterfacePositionContext(
                typed_name=local_def.typed_name.source_typed_name,
                constraints=self._converter.constraints_to_class_references(
                    local_def.constraints,
                ),
            )
            for local_def in self._definition.interface_positions
        ]

        trigger_position_name = self._definition.trigger_conditions.conditions[
            0
        ].typed_name.source_typed_name

        interface_position_names = {
            local_def.typed_name.source_typed_name
            for local_def in self._definition.interface_positions
        }

        block_gen = action_statements.ActionStatementsBlockGenerator(
            self._definition.action_statements,
            self._definition.typed_name,
            self._converter,
            interface_position_names=interface_position_names,
        )

        implied_qualities = self._converter.implied_qualities_to_class_references(
            self._definition.quality_implications,
        )

        return template_context.ActionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.source_typed_name,
            module_name=module_name,
            interface_positions=interface_positions,
            trigger_position_name=trigger_position_name,
            body_statements=block_gen.generate(),
            implied_qualities=implied_qualities,
        )
