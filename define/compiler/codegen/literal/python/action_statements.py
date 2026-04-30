"""Python code generator for action statements blocks."""

from define.compiler import ast
from define.compiler.codegen.literal.python import naming, template_context


class ActionStatementsBlockGenerator:
    """Extracts template data from an action statements block."""

    _block: ast.ActionStatementsBlock
    _converter: naming.NameConverter
    _defining_typed_name: ast.GlobalTypedNameInDefinition
    _interface_position_names: set[str]
    _local_names: naming.LocalNameConverter

    def __init__(
        self,
        block: ast.ActionStatementsBlock,
        defining_typed_name: ast.GlobalTypedNameInDefinition,
        converter: naming.NameConverter,
        interface_position_names: set[str] | None = None,
    ):
        """Initialize with the action statements block to generate data for."""
        self._block = block
        self._converter = converter
        self._defining_typed_name = defining_typed_name
        self._interface_position_names = interface_position_names or set()
        self._local_names = naming.LocalNameConverter()

    def generate(self) -> list[template_context.ActionStatementContext]:
        """Generate template data for all statements in the block."""
        return [self._build_statement(stmt) for stmt in self._block.statements]

    def _build_statement(
        self, stmt: ast.ActionStatement
    ) -> template_context.ActionStatementContext:
        if isinstance(stmt, ast.LocalPositionDefinition):
            return template_context.ActionStatementContext(
                kind=template_context.StatementKind.LOCAL_POSITION,
                local_var_name=self._local_names.convert(
                    stmt.typed_name.name_content.name
                ),
                local_typed_name=stmt.typed_name.source_typed_name,
                constraints=self._converter.constraints_to_class_references(
                    stmt.constraints,
                ),
            )
        if isinstance(stmt, ast.CreateDimensionPointStatement):
            return template_context.ActionStatementContext(
                kind=template_context.StatementKind.CREATE_DIMENSION_POINT,
                position=self._build_position_expr(stmt.target_position),
            )
        if isinstance(stmt, ast.DestroyDimensionPointStatement):
            return template_context.ActionStatementContext(
                kind=template_context.StatementKind.DESTROY_DIMENSION_POINT,
                position=self._build_position_expr(stmt.target_position),
            )
        return template_context.ActionStatementContext(
            kind=template_context.StatementKind.MOVE_DIMENSION_POINT,
            position=self._build_position_expr(stmt.source_position),
            to_position=self._build_position_expr(stmt.target_position),
        )

    def _build_position_expr(
        self, position_reference: ast.PositionReference
    ) -> template_context.PositionExpr:
        """Build a position expression from a position reference chain."""
        first = position_reference.typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            if first.source_typed_name in self._interface_position_names:
                start = "self"
                chain_elements: list[template_context.ChainElement] = [
                    template_context.ChainElement(
                        accessor=template_context.ChainAccessor.POSITION_FROM_ACTION,
                        typed_name=first.source_typed_name,
                    )
                ]
            else:
                start = self._local_names.convert(first.name_content.name)
                chain_elements = []
        else:
            start = "self"
            chain_elements = []
        for i, elem in enumerate(position_reference.typed_names[1:]):
            prev = position_reference.typed_names[i]
            chain_elements.append(
                template_context.ChainElement(
                    accessor=_chain_accessor(prev.name_type, elem.name_type),
                    typed_name=elem.full_typed_name,
                )
            )
        return template_context.PositionExpr(start=start, chain_elements=chain_elements)


def _chain_accessor(
    prev_type: ast.NameType, current_type: ast.NameType
) -> template_context.ChainAccessor:
    if prev_type == ast.NameType.ACTION:
        return template_context.ChainAccessor.POSITION_FROM_ACTION
    if current_type == ast.NameType.ACTION:
        return template_context.ChainAccessor.ACTION_FROM_POSITION
    return template_context.ChainAccessor.POSITION_FROM_POSITION
