"""Python code generator for action statements blocks."""

from define.compiler import ast


class ActionStatementsBlockGenerator:
    """Generates Python code for an action statements block."""

    _block: ast.ActionStatementsBlock

    def __init__(self, block: ast.ActionStatementsBlock):
        """Initialize with the action statements block to generate code for."""
        self._block = block

    def generate(self) -> str:
        """Generate Python code for all statements in the block."""
        lines: list[str] = []
        for stmt in self._block.statements:
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
