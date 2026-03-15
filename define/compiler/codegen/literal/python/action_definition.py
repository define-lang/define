"""Python code generator data for action definitions."""

from dataclasses import dataclass

from define.compiler import ast
from define.compiler.codegen.literal.python import naming


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    typed_name: str


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

        return ActionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.full_typed_name(),
        )
