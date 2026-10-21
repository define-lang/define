"""Python code generator for position definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.codegen.literal.python import (
    renderer,
    value_types,
)

if TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.codegen.literal.python import (
        naming,
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

    def generate(self) -> renderer.PositionDefinition:
        """Generate template context for the position definition."""
        name_content = self._definition.typed_name.name_content
        constraints = self._converter.constraints_to_class_references(
            self._definition.constraints,
        )
        class_name = self._converter.class_name(self._definition.typed_name)
        module_name = self._converter.module_name(name_content)
        imports = {class_reference.module_name for class_reference in constraints}
        # Classes in the definition's own module are referenced by their bare
        # names, and a module cannot import itself while it is still loading.
        imports.discard(module_name)

        return renderer.PositionDefinition(
            class_name=class_name,
            module_name=module_name,
            constraints=constraints,
            value_type=value_types.constrained_python_value_type(
                self._definition.constraints
            ),
            imports=imports,
        )
