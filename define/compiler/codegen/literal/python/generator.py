"""Python literal code generator for the Define compiler."""

from pathlib import Path
from typing import cast

from define.compiler import ast
from define.compiler.validator import validation_result

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "python"
_MAIN_TEMPLATE = (_TEMPLATES_DIR / "main.txt").read_text()


class PythonLiteralCodeGenerator:
    """Generates literal Python code for a validated Define entry point."""

    def generate_entry_point(
        self, entry_point_result: validation_result.DefinitionValidationResult
    ) -> str:
        """Generate Python code for the entry point position."""
        definition = cast("ast.PositionDefinition", entry_point_result.definition)

        fqun = definition.typed_name.name_content.fqun
        full_name = definition.typed_name.name_content.full_name()

        super_init = self._generate_super_init(full_name, definition, fqun)
        after_assigned = self._generate_after_assigned(definition, fqun)
        typing_import = "\nfrom typing import override\n" if after_assigned else ""

        return _MAIN_TEMPLATE.format(
            typing_import=typing_import,
            super_init=super_init,
            after_assigned=after_assigned,
        )

    def _generate_super_init(
        self,
        full_name: str,
        definition: ast.PositionDefinition,
        fqun: ast.Fqun,
    ) -> str:
        constraints = self._get_constraints(definition, fqun)
        if not constraints:
            return f'        super().__init__("{full_name}")'
        constraint_strs = ", ".join(f'"{c}"' for c in constraints)
        return (
            f"        super().__init__(\n"
            f'            "{full_name}",\n'
            f"            constraints=[{constraint_strs}],\n"
            f"        )"
        )

    def _generate_after_assigned(
        self, definition: ast.PositionDefinition, fqun: ast.Fqun
    ) -> str:
        if definition.initialization is None:
            return ""
        lines: list[str] = ["", "", "    @override", "    def after_assigned(self):"]
        for stmt in definition.initialization.statements:
            lines.append(self._generate_statement(stmt, fqun))
        return "\n".join(lines)

    def _get_constraints(
        self, definition: ast.PositionDefinition, fqun: ast.Fqun
    ) -> list[str]:
        if definition.constraints is None:
            return []
        return [
            req.typed_global_name.full_typed_name(in_universe=fqun)
            for req in definition.constraints.requirements
        ]

    def _generate_statement(
        self,
        stmt: ast.ActionStatement,
        fqun: ast.Fqun,
    ) -> str:
        if isinstance(stmt, ast.LocalPositionDefinition):
            return self._generate_local_position(stmt, fqun)
        if isinstance(stmt, ast.CreateDimensionPointStatement):
            var = self._position_ref_to_var(stmt.position_reference)
            return f"        _ = {var}.create_dimension_point()"
        from_var = self._position_ref_to_var(stmt.from_position)
        to_var = self._position_ref_to_var(stmt.to_position)
        return f"        {from_var}.move_dimension_point_to({to_var})"

    def _generate_local_position(
        self, stmt: ast.LocalPositionDefinition, fqun: ast.Fqun
    ) -> str:
        local_name = stmt.typed_name.name_content.name
        if stmt.constraints is not None:
            constraints = [
                req.typed_global_name.full_typed_name(in_universe=fqun)
                for req in stmt.constraints.requirements
            ]
            constraint_strs = ", ".join(f'"{c}"' for c in constraints)
            return f'        {local_name} = literal.Position("{local_name}", constraints=[{constraint_strs}])'
        return f'        {local_name} = literal.Position("{local_name}")'

    def _position_ref_to_var(self, ref: ast.PositionReference) -> str:
        typed_name = ref.chain.typed_names[0]
        if isinstance(typed_name, ast.GlobalTypedNameReference):
            return "self"
        return typed_name.name_content.name
