"""Python code generator for position definitions."""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from define.compiler import ast
from define.compiler.codegen.literal.python import (
    action_statements,
)


def _path_to_class_name(path: PurePosixPath) -> str:
    """Convert a position path to a PascalCase class name."""
    return "".join(
        part.capitalize() for segment in path.parts for part in segment.split("_")
    )


@dataclass
class PositionDefinitionResult:
    """Result of generating a position definition class."""

    class_name: str
    class_body: str
    typing_imports: list[str] = field(default_factory=list)


class PositionDefinitionGenerator:
    """Generates Python code for a position definition class."""

    _definition: ast.PositionDefinition

    def __init__(self, definition: ast.PositionDefinition):
        """Initialize with the position definition to generate code for."""
        self._definition = definition

    def generate(self) -> PositionDefinitionResult:
        """Generate the position definition class body."""
        typing_imports = ["ClassVar"]

        class_vars = self._generate_class_vars()
        after_assigned = self._generate_after_assigned()
        if after_assigned:
            typing_imports.append("override")

        class_name = _path_to_class_name(
            self._definition.typed_name.name_content.path.relative_path
        )

        return PositionDefinitionResult(
            class_name=class_name,
            class_body=class_vars + after_assigned,
            typing_imports=typing_imports,
        )

    def _generate_class_vars(self) -> str:
        typed_name = self._definition.typed_name.full_typed_name()
        return f'    _typed_name: ClassVar[str] = "{typed_name}"'

    def _generate_after_assigned(self) -> str:
        if self._definition.initialization is None:
            return ""
        block_gen = action_statements.ActionStatementsBlockGenerator(
            self._definition.initialization,
            self._definition.typed_name,
        )
        lines: list[str] = [
            "",
            "",
            "    @override",
            "    def after_assigned(self):",
            block_gen.generate(),
        ]
        return "\n".join(lines)
