"""Python code generator for position definitions."""

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    naming,
    template_context,
)


class PositionDefinitionGenerator:
    """Extracts template context from a position definition."""

    _converter: naming.NameConverter
    _definition: ast.PositionDefinition

    def __init__(
        self,
        definition: ast.PositionDefinition,
        converter: naming.NameConverter,
    ):
        """Initialize with the position definition to extract data from."""
        self._definition = definition
        self._converter = converter

    def generate(self) -> template_context.PositionDefinitionContext:
        """Generate template context for the position definition."""
        name_content = self._definition.typed_name.name_content
        constraints = self._converter.constraints_to_class_references(
            self._definition.constraints,
        )
        implied_qualities = self._converter.implied_qualities_to_class_references(
            self._definition.quality_implications,
        )

        class_name = self._converter.class_name(name_content.path.relative_path)
        module_name = self._converter.module_name(name_content)

        return template_context.PositionDefinitionContext(
            class_name=class_name,
            module_name=module_name,
            constraints=constraints,
            implied_qualities=implied_qualities,
        )
