"""Template context dataclasses for Python literal code generation."""

import enum
from dataclasses import InitVar, dataclass, field

from define.compiler import ast
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
    CREATE_PARTICLE = enum.auto()
    MOVE_PARTICLE = enum.auto()
    DESTROY_PARTICLE = enum.auto()


class ChainAccessor(enum.Enum):
    """How to access a chain element from the previous element."""

    POSITION_FROM_POSITION = enum.auto()
    ACTION_FROM_POSITION = enum.auto()
    POSITION_FROM_ACTION = enum.auto()
    IMPLIED_ACTION = enum.auto()
    IMPLIED_POSITION = enum.auto()


@dataclass
class ChainElement:
    """An element in a position reference chain."""

    previous_name_type: InitVar[ast.NameType | None]
    name_type: InitVar[ast.NameType]
    accessor: ChainAccessor = field(init=False)

    def __post_init__(
        self,
        previous_name_type: ast.NameType | None,
        name_type: ast.NameType,
    ):
        """Derive the accessor from this element and its predecessor."""
        if previous_name_type is None:
            if name_type == ast.NameType.ACTION:
                self.accessor = ChainAccessor.IMPLIED_ACTION
            else:
                self.accessor = ChainAccessor.IMPLIED_POSITION
        elif previous_name_type == ast.NameType.ACTION:
            self.accessor = ChainAccessor.POSITION_FROM_ACTION
        elif name_type == ast.NameType.ACTION:
            self.accessor = ChainAccessor.ACTION_FROM_POSITION
        else:
            self.accessor = ChainAccessor.POSITION_FROM_POSITION


@dataclass
class GlobalQualityChainElement(ChainElement):
    """A global quality in a position reference chain."""

    class_reference: naming.ClassReference


@dataclass
class InterfacePositionChainElement(ChainElement):
    """An interface position in a position reference chain."""

    typed_name: str


@dataclass
class PositionExpr:
    """A position expression for use in templates."""

    start: str
    chain_elements: list[ChainElement] = field(default_factory=list)

    @property
    def class_references(self) -> tuple[naming.ClassReference, ...]:
        """Return global classes referenced by this expression."""
        return tuple(
            element.class_reference
            for element in self.chain_elements
            if isinstance(element, GlobalQualityChainElement)
        )


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
    module_name: str
    interface_positions: list[InterfacePositionContext] = field(default_factory=list)
    trigger_position_name: str = ""
    is_constructor: bool = False
    is_destructor: bool = False
    body_statements: list[ActionStatementContext] = field(default_factory=list)
    implied_qualities: list[naming.ClassReference] = field(default_factory=list)

    @property
    def needs_override(self) -> bool:
        """Whether the generated class needs the @override decorator."""
        return True

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.is_constructor or self.is_destructor or self.implied_qualities)

    @property
    def imports(self) -> list[naming.ClassReference]:
        """Deduplicated, sorted imports needed by this definition."""
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.implied_qualities)
        for iface in self.interface_positions:
            class_references.extend(iface.constraints)
        for stmt in self.body_statements:
            class_references.extend(stmt.constraints)
            if stmt.position is not None:
                class_references.extend(stmt.position.class_references)
            if stmt.to_position is not None:
                class_references.extend(stmt.to_position.class_references)
        return _compute_imports(class_references, self.module_name)


@dataclass
class PositionDefinitionContext:
    """Template context for rendering a position definition class."""

    class_name: str
    module_name: str
    constraints: list[naming.ClassReference] = field(default_factory=list)
    implied_qualities: list[naming.ClassReference] = field(default_factory=list)

    @property
    def needs_override(self) -> bool:
        """Whether the generated class needs the @override decorator."""
        return False

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.constraints or self.implied_qualities)

    @property
    def imports(self) -> list[naming.ClassReference]:
        """Deduplicated, sorted imports needed by this definition."""
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.constraints)
        class_references.extend(self.implied_qualities)
        return _compute_imports(class_references, self.module_name)
