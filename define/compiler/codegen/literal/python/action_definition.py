"""Python code generator data for action definitions."""

from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
    naming,
)


@dataclass
class InterfacePositionContext:
    """Template context for an interface position in an action definition."""

    typed_name: str
    constraint_class_names: list[str] = field(default_factory=list)


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    typed_name: str
    has_body: bool = False
    interface_positions: list[InterfacePositionContext] = field(default_factory=list)
    trigger_position_name: str = ""
    body_statements: list[action_statements.StatementData] = field(default_factory=list)


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

    def generate(self) -> ActionDefinitionContext:
        """Generate template context for the action definition."""
        class_name = self._converter.class_name(
            self._definition.typed_name.name_content.path.relative_path
        )

        block = self._definition.definition_block
        if block is None:
            return ActionDefinitionContext(
                class_name=class_name,
                typed_name=self._definition.typed_name.full_typed_name(),
            )

        interface_positions = [
            InterfacePositionContext(
                typed_name=local_def.typed_name.source_typed_name,
                constraint_class_names=self._converter.constraints_to_class_names(
                    local_def.constraints
                ),
            )
            for local_def in block.local_definitions
        ]

        trigger_position_name = (
            block.trigger_conditions.conditions[0]
            .position_reference.chain.typed_names[0]
            .source_typed_name
        )

        interface_position_names = {
            local_def.typed_name.source_typed_name
            for local_def in block.local_definitions
        }

        block_gen = action_statements.ActionStatementsBlockGenerator(
            block.action_statements,
            self._definition.typed_name,
            self._converter,
            interface_position_names=interface_position_names,
        )

        return ActionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.full_typed_name(),
            has_body=True,
            interface_positions=interface_positions,
            trigger_position_name=trigger_position_name,
            body_statements=block_gen.generate(),
        )
