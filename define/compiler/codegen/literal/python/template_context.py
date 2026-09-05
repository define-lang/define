"""Template context dataclasses for Python literal code generation."""

from __future__ import annotations

import enum
from dataclasses import InitVar, dataclass, field
from typing import TYPE_CHECKING

from define.compiler import ast

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from define.compiler.codegen.literal.python import naming
    from define.compiler.validator.reference_graph import operation_graph_labeler


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

    local_position_member_name: str | None
    chain_elements: list[ChainElement]

    def referenced_module_names(self) -> Iterator[str]:
        """Yield external modules referenced by this expression."""
        for element in self.chain_elements:
            if isinstance(element, GlobalQualityChainElement):
                yield element.class_reference.module_name


@dataclass
class ActionStatementContext:
    """Template-friendly representation of an action statement."""

    kind: StatementKind
    local_position_member_name: str | None = None
    local_typed_name: str | None = None
    constraints: list[naming.ClassReference] = field(default_factory=list)
    position: PositionExpr | None = None
    to_position: PositionExpr | None = None
    operation_label: operation_graph_labeler.OperationLabel | None = None
    destruction_connection_name: str | None = None


@dataclass
class DestructionContinuationContext:
    """A generated reference to one callee destruction continuation."""

    execution_class: naming.ClassReference
    member_name: str


@dataclass
class ActionFragmentContext:
    """Template context for one directly called action fragment."""

    method_name: str
    statements: list[ActionStatementContext]
    inits: InitContext
    fanout_continuation_method_names: list[str]
    inline_callee_binding_plans: list[CalleeBindingPlanContext]
    guarantee_name: str | None
    dependency_count: int
    join_is_assigned_by_caller: bool
    requires_join_check: bool
    join_member_name: str | None
    continue_destroy_method_name: str | None
    guarantee_dependent_destroy_position: DestructionPositionContext | None


@dataclass
class DestructionContractDestructorExecutionContext:
    """One Destructor Action Execution contributed through a Destruction Contract."""

    execution_class: naming.ClassReference
    run_method_name: str
    action_parent_binding_method_name: str
    guarantee_names_completing_connection: list[str]
    trace_action_name: str | None


@dataclass
class DestructionConnectionContext:
    """One destruction connection created for a direct callee."""

    member_name: str
    destruction_continuation: DestructionContinuationContext
    start_method_names: list[str]
    destruction_contract_destructors: list[
        DestructionContractDestructorExecutionContext
    ]
    predecessor_count: int


@dataclass
class DestructionPositionContext:
    """A caller-known position used by a contributed Destroy."""

    member_name: str
    position: PositionExpr


@dataclass
class TriggeredActionExecutionContext:
    """One direct Action Execution used by generated dependency wiring."""

    action_expression: PositionExpr | None
    execution_class: naming.ClassReference
    execution_name: str
    callee_join_assignments: list[CalleeJoinAssignmentContext]
    guarantee_consumptions: Sequence[GuaranteeConsumptionContext]
    created_destruction_connections: list[DestructionConnectionContext]
    forwards_destruction_connections: bool
    trace_parent_action_name: str | None
    trace_action_name: str | None = None

    @property
    def execution_needs_action(self) -> bool:
        """Whether the triggered execution receives its Action instance."""
        return self.action_expression is not None


@dataclass
class InitContext:
    """Generated runtime-state init performed synchronously."""

    action_executions: list[TriggeredActionExecutionContext]
    callee_binding_method_names: list[str]


@dataclass(frozen=True, slots=True)
class CalleeJoinAssignmentContext:
    """One caller-selected Join assigned through a generated execution path."""

    member_name: str
    dependency_count: int
    execution_member_names: list[str]


@dataclass
class GuaranteeConsumptionContext:
    """Generated tasks that consume one Guarantee."""

    execution_member_names: list[str]
    guarantee_name: str
    init_method_name: str | None
    consumer_method_names: list[str]


@dataclass
class DeferredGuaranteeRegistrationContext:
    """A Guarantee registration performed after its execution path exists."""

    method_name: str
    consumption: GuaranteeConsumptionContext


@dataclass
class GuaranteesContext:
    """Generated guarantees for one action execution."""

    class_name: str
    guarantee_names: Iterable[str]


@dataclass
class CalleeBindingPlanContext:
    """Generated context for completing one direct Callee Binding."""

    action_execution_name: str
    callee_binding_hole_method_name: str
    callee_continuation_method_name: str | None
    method_name: str | None
    invocation_method_name: str | None
    invokes_callee_binding_hole: bool
    dependency_count: int
    join_is_assigned_by_caller: bool
    requires_join_check: bool
    join_member_name: str | None
    destruction_positions: list[DestructionPositionContext]
    init_method_name: str | None
    post_init_join_assignments: list[CalleeJoinAssignmentContext]
    post_init_guarantee_consumptions: list[GuaranteeConsumptionContext]


@dataclass
class BindingHoleFanoutContext:
    """Generated init and runnable fanout for one Binding Hole."""

    binding_hole_method_name: str
    requires_join_check: bool
    join_member_name: str | None
    inits: InitContext
    separate_init_method_name: str | None
    continuation_method_name: str | None
    fanout_continuation_method_names: list[str]


@dataclass
class InitMethodContext:
    """A generated method that performs one init plan."""

    method_name: str
    inits: InitContext


@dataclass
class ActionExecutionContext:
    """Template context for operation-graph execution of one action."""

    execution_class_name: str
    local_position_statements: list[ActionStatementContext]
    destruction_positions: list[DestructionPositionContext]
    fragments: list[ActionFragmentContext]
    binding_hole_fanouts: list[BindingHoleFanoutContext]
    action_executions: list[TriggeredActionExecutionContext]
    creation_inits: InitContext
    init_methods: list[InitMethodContext]
    callee_binding_plans: list[CalleeBindingPlanContext]
    guarantees: GuaranteesContext | None
    accepts_destruction_connections: bool
    trace_operations: bool = False
    deferred_guarantee_registrations: list[DeferredGuaranteeRegistrationContext] = (
        field(default_factory=list)
    )
    needs_action: bool = field(init=False)

    def __post_init__(self):
        """Determine whether this execution accesses its Action instance."""
        for fragment in self.fragments:
            for statement in fragment.statements:
                if (
                    statement.position is not None
                    and statement.position.local_position_member_name is None
                ):
                    self.needs_action = True
                    return
                if (
                    statement.to_position is not None
                    and statement.to_position.local_position_member_name is None
                ):
                    self.needs_action = True
                    return
        self.needs_action = False
        for triggered_action in self.action_executions:
            action_expression = triggered_action.action_expression
            if (
                action_expression is not None
                and action_expression.local_position_member_name is None
            ):
                self.needs_action = True
                return

    @property
    def needs_tracing(self) -> bool:
        """Whether generated code imports the tracing runtime."""
        if not self.trace_operations:
            return False
        for action_execution in self.action_executions:
            if action_execution.created_destruction_connections:
                return True
        return False

    @property
    def needs_guarantees(self) -> bool:
        """Whether this execution publishes or consumes guarantees."""
        return self.guarantees is not None


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
