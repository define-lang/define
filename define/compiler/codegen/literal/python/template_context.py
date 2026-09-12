"""Template context dataclasses for Python literal code generation."""

from __future__ import annotations

import enum
from dataclasses import InitVar, dataclass, field
from typing import TYPE_CHECKING, ClassVar

from define.compiler import ast

if TYPE_CHECKING:
    from define.compiler.codegen.literal.python import naming


class StatementKind(enum.Enum):
    """Discriminator for statement types in templates."""

    LOCAL_POSITION = enum.auto()
    CREATE_PARTICLE = enum.auto()
    MOVE_PARTICLE = enum.auto()
    DESTROY_PARTICLE = enum.auto()
    RUN_ACTION = enum.auto()
    RUN_CONTRACT_DESTRUCTORS = enum.auto()
    DESTROY_CONTRACT_CHILDREN = enum.auto()


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

    local_position_name: str | None
    chain_elements: list[ChainElement]
    from_contract_particle: bool = False


@dataclass
class DestructionContractArgument:
    """A per-invocation contract object and the contributions it forwards."""

    class_name: str
    forwarded_methods: list[str]


@dataclass
class ForwardedContribution:
    """A caller contribution applied to its contracted particle."""

    method_name: str
    position: PositionExpr | None


@dataclass
class DestructionContractMethod:
    """One named contribution to a callee's destruction."""

    name: str
    forwarded: list[ForwardedContribution]
    statements: list[ActionStatementContext]


@dataclass
class DestructionContractDefinition:
    """Methods implementing caller-contributed destruction work."""

    class_name: str
    base: naming.ClassReference
    forwarded_methods: list[str]
    methods: list[DestructionContractMethod]


class ActionStatementContext:
    """Template-friendly representation of an action statement."""

    kind: ClassVar[StatementKind]


@dataclass
class LocalPositionContext(ActionStatementContext):
    """A local position definition."""

    kind: ClassVar[StatementKind] = StatementKind.LOCAL_POSITION
    local_position_name: str
    local_typed_name: str
    constraints: list[naming.ClassReference]


@dataclass(kw_only=True)
class ParticleOperationContext(ActionStatementContext):
    """An operation on a particle, optionally recorded in a trace."""

    position: PositionExpr
    operation_label: str | None = None


@dataclass(kw_only=True)
class CreateParticleContext(ParticleOperationContext):
    """Create a particle at a position."""

    kind: ClassVar[StatementKind] = StatementKind.CREATE_PARTICLE


@dataclass(kw_only=True)
class MoveParticleContext(ParticleOperationContext):
    """Move a particle between positions."""

    kind: ClassVar[StatementKind] = StatementKind.MOVE_PARTICLE
    to_position: PositionExpr


@dataclass(kw_only=True)
class DestroyParticleContext(ParticleOperationContext):
    """Destroy a particle at a position."""

    kind: ClassVar[StatementKind] = StatementKind.DESTROY_PARTICLE


@dataclass
class RunActionContext(ActionStatementContext):
    """Invoke an action with its optional destruction contract."""

    kind: ClassVar[StatementKind] = StatementKind.RUN_ACTION
    position: PositionExpr
    destruction_contract: DestructionContractArgument | None = None


@dataclass
class ContractContributionContext(ActionStatementContext):
    """Invoke a contribution for a contracted particle."""

    position: PositionExpr
    contract_method: str


@dataclass
class RunContractDestructorsContext(ContractContributionContext):
    """Run caller-contributed Destructors."""

    kind: ClassVar[StatementKind] = StatementKind.RUN_CONTRACT_DESTRUCTORS


@dataclass
class DestroyContractChildrenContext(ContractContributionContext):
    """Destroy caller-contributed child particles."""

    kind: ClassVar[StatementKind] = StatementKind.DESTROY_CONTRACT_CHILDREN


@dataclass
class InterfacePositionContext:
    """Template context for an interface position in an action definition."""

    typed_name: str
    constraints: list[naming.ClassReference]


@dataclass
class PositionDefinitionContext:
    """Template context for rendering a position definition class."""

    class_name: str
    module_name: str
    constraints: list[naming.ClassReference]
    implied_qualities: list[naming.ClassReference]

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.constraints or self.implied_qualities)

    @property
    def imports(self) -> list[str]:
        """External modules imported by this definition."""
        module_names = {
            class_reference.module_name for class_reference in self.constraints
        }
        module_names.update(
            class_reference.module_name for class_reference in self.implied_qualities
        )
        return sorted(module_names)
