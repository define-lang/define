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
        if isinstance(stmt, ast.CreateParticleStatement):
            return template_context.ActionStatementContext(
                kind=template_context.StatementKind.CREATE_PARTICLE,
                position=self._build_position_expr(stmt.target_position),
            )
        if isinstance(stmt, ast.DestroyParticleStatement):
            return template_context.ActionStatementContext(
                kind=template_context.StatementKind.DESTROY_PARTICLE,
                position=self._build_position_expr(stmt.target_position),
            )
        return template_context.ActionStatementContext(
            kind=template_context.StatementKind.MOVE_PARTICLE,
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
                    template_context.InterfacePositionChainElement(
                        previous_name_type=ast.NameType.ACTION,
                        name_type=first.name_type,
                        typed_name=first.source_typed_name,
                    )
                ]
            else:
                start = self._local_names.convert(first.name_content.name)
                chain_elements = []
        elif first.full_typed_name == self._defining_typed_name.full_typed_name:
            start = "self"
            chain_elements = []
        else:
            start = "self"
            chain_elements = [
                template_context.GlobalQualityChainElement(
                    previous_name_type=None,
                    name_type=first.name_type,
                    class_reference=self._converter.class_reference(first),
                )
            ]
        for i, elem in enumerate(position_reference.typed_names[1:]):
            prev = position_reference.typed_names[i]
            if isinstance(elem, ast.GlobalTypedNameReference):
                chain_element: template_context.ChainElement = (
                    template_context.GlobalQualityChainElement(
                        previous_name_type=prev.name_type,
                        name_type=elem.name_type,
                        class_reference=self._converter.class_reference(elem),
                    )
                )
            else:
                chain_element = template_context.InterfacePositionChainElement(
                    previous_name_type=prev.name_type,
                    name_type=elem.name_type,
                    typed_name=elem.full_typed_name,
                )
            chain_elements.append(chain_element)
        return template_context.PositionExpr(start=start, chain_elements=chain_elements)
