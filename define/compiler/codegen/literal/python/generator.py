"""Python literal code generator for the Define compiler."""

from pathlib import Path
from typing import cast

from define.compiler import ast
from define.compiler.validator import validation_result

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "python"
_MAIN_TEMPLATE = (_TEMPLATES_DIR / "main.txt").read_text()


def _path_to_class_name(path: str) -> str:
    """Convert a position path to a PascalCase class name."""
    segments = path.strip("/").split("/")
    return "".join(
        part.capitalize() for segment in segments for part in segment.split("_")
    )


class PythonLiteralCodeGenerator:
    """Generates literal Python code for a validated Define entry point."""

    def generate_entry_point(
        self, entry_point_result: validation_result.DefinitionValidationResult
    ) -> str:
        """Generate Python code for the entry point position."""
        definition = cast("ast.PositionDefinition", entry_point_result.definition)

        full_name = definition.typed_name.name_content.full_name()
        path = definition.typed_name.name_content.path.name
        class_name = _path_to_class_name(path)

        class_vars = self._generate_class_vars(full_name)
        after_assigned = self._generate_after_assigned(definition)
        typing_names = ["ClassVar"]
        if after_assigned:
            typing_names.append("override")
        typing_import = f"\nfrom typing import {', '.join(typing_names)}\n"

        return _MAIN_TEMPLATE.format(
            typing_import=typing_import,
            class_name=class_name,
            class_vars=class_vars,
            after_assigned=after_assigned,
        )

    def _generate_class_vars(self, full_name: str) -> str:
        return f'    _typed_name: ClassVar[str] = "position<{full_name}>"'

    def _generate_after_assigned(self, definition: ast.PositionDefinition) -> str:
        if definition.initialization is None:
            return ""
        lines: list[str] = ["", "", "    @override", "    def after_assigned(self):"]
        for stmt in definition.initialization.statements:
            lines.append(self._generate_statement(stmt))
        return "\n".join(lines)

    def _generate_statement(self, stmt: ast.ActionStatement) -> str:
        if isinstance(stmt, ast.LocalPositionDefinition):
            return self._generate_local_position(stmt)
        if isinstance(stmt, ast.CreateDimensionPointStatement):
            var = self._position_ref_to_var(stmt.position_reference)
            return f"        {var}.create_dimension_point()"
        from_var = self._position_ref_to_var(stmt.from_position)
        to_var = self._position_ref_to_var(stmt.to_position)
        return f"        {from_var}.move_dimension_point_to({to_var})"

    def _generate_local_position(self, stmt: ast.LocalPositionDefinition) -> str:
        local_name = stmt.typed_name.name_content.name
        return f'        {local_name} = literal.LocalPosition("{local_name}")'

    def _position_ref_to_var(self, ref: ast.PositionReference) -> str:
        typed_name = ref.chain.typed_names[0]
        if isinstance(typed_name, ast.GlobalTypedNameReference):
            return "self"
        return typed_name.name_content.name
