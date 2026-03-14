"""Python code generator data for action statements blocks."""

import enum
from dataclasses import dataclass, field

from define.compiler import ast


class StatementKind(enum.Enum):
    """Discriminator for statement types in templates."""

    LOCAL_POSITION = enum.auto()
    CREATE_DIMENSION_POINT = enum.auto()
    MOVE_DIMENSION_POINT = enum.auto()


@dataclass
class PositionExpr:
    """A position expression for use in templates."""

    start: str
    chain_elements: list[str] = field(default_factory=list)


@dataclass
class StatementData:
    """Template-friendly representation of an action statement."""

    kind: StatementKind
    local_name: str | None = None
    position: PositionExpr | None = None
    to_position: PositionExpr | None = None


class ActionStatementsBlockGenerator:
    """Extracts template data from an action statements block."""

    _block: ast.ActionStatementsBlock
    _defining_typed_name: ast.GlobalTypedNameInDefinition

    def __init__(
        self,
        block: ast.ActionStatementsBlock,
        defining_typed_name: ast.GlobalTypedNameInDefinition,
    ):
        """Initialize with the action statements block to generate data for."""
        self._block = block
        self._defining_typed_name = defining_typed_name

    def generate(self) -> list[StatementData]:
        """Generate template data for all statements in the block."""
        return [self._build_statement(stmt) for stmt in self._block.statements]

    def _build_statement(self, stmt: ast.ActionStatement) -> StatementData:
        if isinstance(stmt, ast.LocalPositionDefinition):
            return StatementData(
                kind=StatementKind.LOCAL_POSITION,
                local_name=stmt.typed_name.name_content.name,
            )
        if isinstance(stmt, ast.CreateDimensionPointStatement):
            return StatementData(
                kind=StatementKind.CREATE_DIMENSION_POINT,
                position=self._build_position_expr(stmt.position_reference),
            )
        return StatementData(
            kind=StatementKind.MOVE_DIMENSION_POINT,
            position=self._build_position_expr(stmt.from_position),
            to_position=self._build_position_expr(stmt.to_position),
        )

    def _build_position_expr(self, ref: ast.PositionReference) -> PositionExpr:
        """Build a position expression from a position reference chain."""
        fqun = self._defining_typed_name.name_content.fqun
        chain = ref.chain
        first = chain.typed_names[0]
        if isinstance(first, ast.LocalTypedNameReference):
            start = first.name_content.name
        else:
            start = "self"
        chain_elements = [
            elem.full_typed_name(in_universe=fqun) for elem in chain.typed_names[1:]
        ]
        return PositionExpr(start=start, chain_elements=chain_elements)
