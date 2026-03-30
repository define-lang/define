"""Python code generator for position definitions."""

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
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
        has_init = self._definition.initialization is not None
        name_content = self._definition.typed_name.name_content
        enclosing_fqun = name_content.fqun
        constraint_refs = self._converter.constraints_to_refs(
            self._definition.constraints,
            enclosing_fqun,
        )

        statements: list[template_context.ActionStatementContext] = []
        if self._definition.initialization is not None:
            block_gen = action_statements.ActionStatementsBlockGenerator(
                self._definition.initialization,
                self._definition.typed_name,
                self._converter,
            )
            statements = block_gen.generate()

        class_name = self._converter.class_name(name_content.path.relative_path)
        module_name = self._converter.module_name(name_content)

        return template_context.PositionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.source_typed_name,
            has_init=has_init,
            module_name=module_name,
            constraint_refs=constraint_refs,
            statements=statements,
        )
