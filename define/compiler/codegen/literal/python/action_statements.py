"""Python code generator data for action statements blocks."""

import enum
from dataclasses import dataclass, field

from define.compiler import ast
from define.compiler.codegen.literal.python import naming


class StatementKind(enum.Enum):
    """Discriminator for statement types in templates."""

    LOCAL_POSITION = enum.auto()
    CREATE_DIMENSION_POINT = enum.auto()
    MOVE_DIMENSION_POINT = enum.auto()


class ChainAccessor(enum.Enum):
    """How to access a chain element from the previous element."""

    POSITION_FROM_POSITION = enum.auto()
    ACTION_FROM_POSITION = enum.auto()
    POSITION_FROM_ACTION = enum.auto()


@dataclass
class ChainElement:
    """A single element in a position reference chain."""

    accessor: ChainAccessor
    typed_name: str


@dataclass
class PositionExpr:
    """A position expression for use in templates."""

    start: str
    chain_elements: list[ChainElement] = field(default_factory=list)


@dataclass
class StatementData:
    """Template-friendly representation of an action statement."""

    kind: StatementKind
    local_var_name: str | None = None
    local_typed_name: str | None = None
    constraint_class_names: list[str] = field(default_factory=list)
    position: PositionExpr | None = None
    to_position: PositionExpr | None = None


class ActionStatementsBlockGenerator:
    """Extracts template data from an action statements block."""

    _block: ast.ActionStatementsBlock
    _defining_typed_name: ast.GlobalTypedNameInDefinition
    _interface_position_names: set[str]

    def __init__(
        self,
        block: ast.ActionStatementsBlock,
        defining_typed_name: ast.GlobalTypedNameInDefinition,
        interface_position_names: set[str] | None = None,
    ):
        """Initialize with the action statements block to generate data for."""
        self._block = block
        self._defining_typed_name = defining_typed_name
        self._interface_position_names = interface_position_names or set()

    def generate(self) -> list[StatementData]:
        """Generate template data for all statements in the block."""
        return [self._build_statement(stmt) for stmt in self._block.statements]

    def _build_statement(self, stmt: ast.ActionStatement) -> StatementData:
        if isinstance(stmt, ast.LocalPositionDefinition):
            return StatementData(
                kind=StatementKind.LOCAL_POSITION,
                local_var_name=stmt.typed_name.name_content.name,
                local_typed_name=stmt.typed_name.source_typed_name,
                constraint_class_names=naming.constraints_to_class_names(
                    stmt.constraints
                ),
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
            if first.source_typed_name in self._interface_position_names:
                start = "self"
                chain_elements: list[ChainElement] = [
                    ChainElement(
                        accessor=ChainAccessor.POSITION_FROM_ACTION,
                        typed_name=first.source_typed_name,
                    )
                ]
            else:
                start = first.name_content.name
                chain_elements = []
        else:
            # This is a self-reference, which only happens in a position init block.
            start = "self"
            chain_elements = []
        for i, elem in enumerate(chain.typed_names[1:]):
            prev = chain.typed_names[i]
            chain_elements.append(
                ChainElement(
                    accessor=_chain_accessor(prev.name_type, elem.name_type),
                    typed_name=elem.full_typed_name(in_universe=fqun),
                )
            )
        return PositionExpr(start=start, chain_elements=chain_elements)


def _chain_accessor(
    prev_type: ast.NameType, current_type: ast.NameType
) -> ChainAccessor:
    if prev_type == ast.NameType.ACTION:
        return ChainAccessor.POSITION_FROM_ACTION
    if current_type == ast.NameType.ACTION:
        return ChainAccessor.ACTION_FROM_POSITION
    return ChainAccessor.POSITION_FROM_POSITION
