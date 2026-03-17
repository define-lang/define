"""Python code generator data for position definitions."""

from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
    naming,
)


@dataclass
class PositionDefinitionContext:
    """Template context for rendering a position definition class."""

    class_name: str
    typed_name: str
    has_init: bool
    constraint_class_names: list[str] = field(default_factory=list)
    statements: list[action_statements.StatementData] = field(default_factory=list)


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

    def generate(self) -> PositionDefinitionContext:
        """Generate template context for the position definition."""
        has_init = self._definition.initialization is not None
        constraint_class_names = self._converter.constraints_to_class_names(
            self._definition.constraints
        )

        statements: list[action_statements.StatementData] = []
        if self._definition.initialization is not None:
            block_gen = action_statements.ActionStatementsBlockGenerator(
                self._definition.initialization,
                self._definition.typed_name,
                self._converter,
            )
            statements = block_gen.generate()

        class_name = self._converter.class_name(
            self._definition.typed_name.name_content.path.relative_path
        )

        return PositionDefinitionContext(
            class_name=class_name,
            typed_name=self._definition.typed_name.full_typed_name(),
            has_init=has_init,
            constraint_class_names=constraint_class_names,
            statements=statements,
        )
