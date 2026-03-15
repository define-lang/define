"""Python code generator data for action definitions."""

from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
    naming,
)


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    typed_name: str
    has_body: bool = False
    interface_positions: list[str] = field(default_factory=list)
    trigger_position_name: str = ""
    body_statements: list[action_statements.StatementData] = field(default_factory=list)


class ActionDefinitionGenerator:
    """Extracts template context from an action definition."""

    _definition: ast.ActionDefinition

    def __init__(self, definition: ast.ActionDefinition):
        """Initialize with the action definition to extract data from."""
        self._definition = definition

    def generate(self) -> ActionDefinitionContext:
        """Generate template context for the action definition."""
        class_name = naming.path_to_class_name(
            self._definition.typed_name.name_content.path.relative_path
        )

        block = self._definition.definition_block
        if block is None:
            return ActionDefinitionContext(
                class_name=class_name,
                typed_name=self._definition.typed_name.full_typed_name(),
            )

        interface_positions = [
            local_def.typed_name.source_typed_name
            for local_def in block.local_definitions
        ]

        trigger_position_name = (
            block.trigger_conditions.conditions[0]
            .position_reference.chain.typed_names[0]
            .source_typed_name
        )

        block_gen = action_statements.ActionStatementsBlockGenerator(
            block.action_statements,
            self._definition.typed_name,
        )

        return ActionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.full_typed_name(),
            has_body=True,
            interface_positions=interface_positions,
            trigger_position_name=trigger_position_name,
            body_statements=block_gen.generate(),
        )
