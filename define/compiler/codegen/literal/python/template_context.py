"""Template context dataclasses for Python literal code generation."""

import enum
from dataclasses import dataclass, field

from define.compiler.codegen.literal.python import naming


def _compute_imports(
    class_references: list[naming.ClassReference], own_module_name: str
) -> list[naming.ClassReference]:
    """Deduplicate and sort imports, excluding self-references."""
    seen: set[str] = set()
    imports: list[naming.ClassReference] = []
    for class_reference in class_references:
        if (
            class_reference.module_name != own_module_name
            and class_reference.module_name not in seen
        ):
            seen.add(class_reference.module_name)
            imports.append(class_reference)
    imports.sort(key=lambda imp: imp.module_name)
    return imports


class StatementKind(enum.Enum):
    """Discriminator for statement types in templates."""

    LOCAL_POSITION = enum.auto()
    CREATE_DIMENSION_POINT = enum.auto()
    MOVE_DIMENSION_POINT = enum.auto()
    DESTROY_DIMENSION_POINT = enum.auto()


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
class ActionStatementContext:
    """Template-friendly representation of an action statement."""

    kind: StatementKind
    local_var_name: str | None = None
    local_typed_name: str | None = None
    constraints: list[naming.ClassReference] = field(default_factory=list)
    position: PositionExpr | None = None
    to_position: PositionExpr | None = None


@dataclass
class InterfacePositionContext:
    """Template context for an interface position in an action definition."""

    typed_name: str
    constraints: list[naming.ClassReference] = field(default_factory=list)


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    typed_name: str
    module_name: str
    interface_positions: list[InterfacePositionContext] = field(default_factory=list)
    trigger_position_name: str = ""
    body_statements: list[ActionStatementContext] = field(default_factory=list)
    quality_requirements: list[naming.ClassReference] = field(default_factory=list)

    @property
    def needs_override(self) -> bool:
        """Whether the generated class needs the @override decorator."""
        return True

    @property
    def imports(self) -> list[naming.ClassReference]:
        """Deduplicated, sorted imports needed by this definition."""
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.quality_requirements)
        for iface in self.interface_positions:
            class_references.extend(iface.constraints)
        for stmt in self.body_statements:
            class_references.extend(stmt.constraints)
        return _compute_imports(class_references, self.module_name)


@dataclass
class PositionDefinitionContext:
    """Template context for rendering a position definition class."""

    class_name: str
    typed_name: str
    has_init: bool
    module_name: str
    constraints: list[naming.ClassReference] = field(default_factory=list)
    quality_requirements: list[naming.ClassReference] = field(default_factory=list)
    statements: list[ActionStatementContext] = field(default_factory=list)

    @property
    def needs_override(self) -> bool:
        """Whether the generated class needs the @override decorator."""
        return self.has_init

    @property
    def imports(self) -> list[naming.ClassReference]:
        """Deduplicated, sorted imports needed by this definition."""
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.constraints)
        class_references.extend(self.quality_requirements)
        for stmt in self.statements:
            class_references.extend(stmt.constraints)
        return _compute_imports(class_references, self.module_name)
