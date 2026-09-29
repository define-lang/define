"""Template context dataclasses for Python literal code generation."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, ClassVar

import msgspec

from define.compiler import name_types

if TYPE_CHECKING:
    from define.compiler.codegen.literal.python import naming


class StatementKind(enum.Enum):
    """Discriminator for statement types in templates."""

    LOCAL_POSITION = enum.auto()
    CREATE_PARTICLE = enum.auto()
    MOVE_PARTICLE = enum.auto()
    DESTROY_PARTICLE = enum.auto()
    SET_VALUE = enum.auto()
    SET_VALUE_FROM = enum.auto()
    RUN_ACTION = enum.auto()
    RUN_CONTRACT_DESTRUCTORS = enum.auto()
    DESTROY_CONTRACT_CHILDREN = enum.auto()
    EXECUTE_OPERATION = enum.auto()


class ChainAccessor(enum.Enum):
    """How to access a chain element from the previous element."""

    POSITION_FROM_POSITION = enum.auto()
    ACTION_FROM_POSITION = enum.auto()
    POSITION_FROM_ACTION = enum.auto()
    IMPLIED_ACTION = enum.auto()
    IMPLIED_POSITION = enum.auto()


class ChainElement:
    """An element in a position reference chain."""

    __slots__: ClassVar[tuple[str, ...]] = ("accessor",)

    accessor: ChainAccessor

    def __init__(
        self,
        previous_name_type: name_types.NameType | None,
        name_type: name_types.NameType,
    ):
        """Derive the accessor from this element and its predecessor."""
        if previous_name_type is None:
            if name_type == name_types.NameType.ACTION:
                self.accessor = ChainAccessor.IMPLIED_ACTION
            else:
                self.accessor = ChainAccessor.IMPLIED_POSITION
        elif previous_name_type == name_types.NameType.ACTION:
            self.accessor = ChainAccessor.POSITION_FROM_ACTION
        elif name_type == name_types.NameType.ACTION:
            self.accessor = ChainAccessor.ACTION_FROM_POSITION
        else:
            self.accessor = ChainAccessor.POSITION_FROM_POSITION


class GlobalQualityChainElement(ChainElement):
    """A global quality in a position reference chain."""

    __slots__: ClassVar[tuple[str, ...]] = ("class_reference",)

    class_reference: naming.ClassReference

    def __init__(
        self,
        previous_name_type: name_types.NameType | None,
        name_type: name_types.NameType,
        class_reference: naming.ClassReference,
    ):
        """Initialize a global quality in a position reference chain."""
        super().__init__(previous_name_type, name_type)
        self.class_reference = class_reference


class InterfacePositionChainElement(ChainElement):
    """An interface position in a position reference chain."""

    __slots__: ClassVar[tuple[str, ...]] = ("typed_name",)

    typed_name: str

    def __init__(
        self,
        previous_name_type: name_types.NameType | None,
        name_type: name_types.NameType,
        typed_name: str,
    ):
        """Initialize an interface position in a position reference chain."""
        super().__init__(previous_name_type, name_type)
        self.typed_name = typed_name


class PositionExpr(msgspec.Struct):
    """A position expression for use in templates."""

    local_position_name: str | None
    chain_elements: list[ChainElement]
    from_contract_particle: bool = False


class DestructionContractArgument(msgspec.Struct):
    """A per-invocation contract object and the contributions it forwards."""

    class_name: str
    forwarded_methods: list[str]


class ForwardedContribution(msgspec.Struct):
    """A caller contribution applied to its contracted particle."""

    method_name: str
    position: PositionExpr | None


class DestructionContractMethod(msgspec.Struct):
    """One named contribution to a callee's destruction."""

    name: str
    forwarded: list[ForwardedContribution]
    statements: list[ActionStatementContext]


class DestructionContractDefinition(msgspec.Struct):
    """Methods implementing caller-contributed destruction work."""

    class_name: str
    base: naming.ClassReference
    forwarded_methods: list[str]
    methods: list[DestructionContractMethod]


class ActionStatementContext(msgspec.Struct, kw_only=True):
    """Template-friendly action statement, optionally recorded in a trace."""

    kind: ClassVar[StatementKind]
    operation_label: str | None = None


class LocalPositionContext(ActionStatementContext):
    """A local position definition."""

    kind: ClassVar[StatementKind] = StatementKind.LOCAL_POSITION
    name: str
    local_typed_name: str
    constraints: list[naming.ClassReference]


class ParticleOperationContext(ActionStatementContext, kw_only=True):
    """An operation on a particle."""

    position: PositionExpr


class CreateParticleContext(ParticleOperationContext, kw_only=True):
    """Create a particle at a position."""

    kind: ClassVar[StatementKind] = StatementKind.CREATE_PARTICLE


class MoveParticleContext(ParticleOperationContext, kw_only=True):
    """Move a particle between positions."""

    kind: ClassVar[StatementKind] = StatementKind.MOVE_PARTICLE
    to_position: PositionExpr


class DestroyParticleContext(ParticleOperationContext, kw_only=True):
    """Destroy a particle at a position."""

    kind: ClassVar[StatementKind] = StatementKind.DESTROY_PARTICLE


class SetValueContext(ParticleOperationContext, kw_only=True):
    """Set the value of a particle from a literal."""

    kind: ClassVar[StatementKind] = StatementKind.SET_VALUE
    value: str


class SetValueFromContext(ParticleOperationContext, kw_only=True):
    """Set the value of a particle from another particle's value."""

    kind: ClassVar[StatementKind] = StatementKind.SET_VALUE_FROM
    source_position: PositionExpr


class RunActionContext(ActionStatementContext):
    """Invoke an action with its optional destruction contract."""

    kind: ClassVar[StatementKind] = StatementKind.RUN_ACTION
    position: PositionExpr
    destruction_contract: DestructionContractArgument | None = None


class ContractContributionContext(ActionStatementContext):
    """Invoke a contribution for a contracted particle."""

    position: PositionExpr
    contract_method: str


class RunContractDestructorsContext(ContractContributionContext):
    """Run caller-contributed Destructors."""

    kind: ClassVar[StatementKind] = StatementKind.RUN_CONTRACT_DESTRUCTORS


class DestroyContractChildrenContext(ContractContributionContext):
    """Destroy caller-contributed child particles."""

    kind: ClassVar[StatementKind] = StatementKind.DESTROY_CONTRACT_CHILDREN


class ExecuteOperationContext(ActionStatementContext):
    """Call the function of the Encoding Operation that an Operation Execution Statement runs."""

    kind: ClassVar[StatementKind] = StatementKind.EXECUTE_OPERATION
    function: naming.FunctionReference
    # A position whose value is read, or a literal already in the view's
    # encoding.
    arguments: list[PositionExpr | str]
    # The positions whose values are set, in the order the function returns
    # them.
    outputs: list[PositionExpr]
    # Local names that hold the returned values when there is more than one.
    result_names: list[str]


class EncodingOperationStatementKind(enum.Enum):
    """Discriminator for statement types in Encoding Operation functions."""

    INFIX_ADD = enum.auto()
    CALL = enum.auto()


class EncodingOperationStatementContext(msgspec.Struct):
    """Template-friendly statement in an Encoding Operation function."""

    kind: ClassVar[EncodingOperationStatementKind]


class InfixAddContext(EncodingOperationStatementContext):
    """Add two values with infix addition."""

    kind: ClassVar[EncodingOperationStatementKind] = (
        EncodingOperationStatementKind.INFIX_ADD
    )
    left: str
    right: str
    result: str


class CallContext(EncodingOperationStatementContext):
    """Call the function of another Encoding Operation."""

    kind: ClassVar[EncodingOperationStatementKind] = EncodingOperationStatementKind.CALL
    function: naming.FunctionReference
    # Local names, or literals already in each view's encoding.
    arguments: list[str]
    # The local names that receive the returned values.
    results: list[str]


class EncodingOperationDefinitionContext(msgspec.Struct):
    """Template context for rendering an Encoding Operation's function."""

    function_name: str
    module_name: str
    parameters: list[str]
    statements: list[EncodingOperationStatementContext]
    results: list[str]
    # Whether the last statement writes exactly the results, so the function
    # returns its expression instead.
    return_last_statement: bool
    imports: list[str]


class InterfacePositionContext(msgspec.Struct):
    """Template context for an interface position in an action definition."""

    typed_name: str
    constraints: list[naming.ClassReference]


class PositionDefinitionContext(msgspec.Struct):
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
        module_names.discard(self.module_name)
        return sorted(module_names)
