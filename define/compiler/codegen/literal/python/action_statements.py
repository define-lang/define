"""Python code generator for action statements blocks."""

from define.compiler import ast


class ActionStatementsBlockGenerator:
    """Generates Python code for an action statements block."""

    _block: ast.ActionStatementsBlock
    _defining_typed_name: ast.GlobalTypedNameInDefinition

    def __init__(
        self,
        block: ast.ActionStatementsBlock,
        defining_typed_name: ast.GlobalTypedNameInDefinition,
    ):
        """Initialize with the action statements block to generate code for."""
        self._block = block
        self._defining_typed_name = defining_typed_name

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
            expr = self._generate_position_expr(stmt.position_reference)
            return f"        {expr}.create_dimension_point()"
        from_expr = self._generate_position_expr(stmt.from_position)
        to_expr = self._generate_position_expr(stmt.to_position)
        return f"        {from_expr}.move_dimension_point_to({to_expr})"

    def _generate_local_position(self, stmt: ast.LocalPositionDefinition) -> str:
        local_name = stmt.typed_name.name_content.name
        return f'        {local_name} = literal.LocalPosition("{local_name}")'

    def _generate_position_expr(self, ref: ast.PositionReference) -> str:
        """Generate the full expression for a position reference chain."""
        fqun = self._defining_typed_name.name_content.fqun
        chain = ref.chain
        first = chain.typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            start = first.name_content.name
        else:
            # The validator guarantees that if there is a global name
            # starting a chain, it only happens in Position Initialization
            # Blocks, and it's always a self-reference.
            start = "self"
        if len(chain.typed_names) == 1:
            return start
        parts = [start]
        for elem in chain.typed_names[1:]:
            typed_name = elem.full_typed_name(in_universe=fqun)
            parts.append(
                f'.dimension_point.get_position(\n            "{typed_name}"\n        )'
            )
        return "".join(parts)
