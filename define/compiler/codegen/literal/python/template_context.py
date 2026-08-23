"""Template context dataclasses for Python literal code generation."""

from __future__ import annotations

import enum
from dataclasses import InitVar, dataclass, field
from typing import TYPE_CHECKING

from define.compiler import ast

if TYPE_CHECKING:
    from collections.abc import Sequence

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

    @property
    def class_references(self) -> list[naming.ClassReference]:
        """Return global classes referenced by this expression."""
        return [
            element.class_reference
            for element in self.chain_elements
            if isinstance(element, GlobalQualityChainElement)
        ]


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
    successor_fragment_method_names: list[str]
    callee_binding_join_method_names_that_depend_on_fragment: list[str]
    triggered_action_successors: list[TriggeredActionExecutionContext]
    triggered_action_execution_callee_binding_join_method_names: list[str]
    guarantee_publication_names: list[str]
    dependency_count: int
    continue_destroy_method_name: str | None
    destruction_connection_names_to_complete: list[str]
    guarantee_dependent_destroy_position: DestructionPositionContext | None


@dataclass
class DestructionContractDestructorExecutionContext:
    """One Destructor Action Execution contributed through a Destruction Contract."""

    execution_class: naming.ClassReference
    trigger_method_name: str
    action_parent_binding_method_name: str
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
    destructor_guarantee_registrations: list[
        DestructionConnectionGuaranteeRegistrationContext
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
    child_guarantees_name: str | None
    created_destruction_connections: list[DestructionConnectionContext]
    forwards_destruction_connections: bool
    trace_parent_action_name: str | None
    trace_action_name: str | None = None

    @property
    def execution_needs_action(self) -> bool:
        """Whether the triggered execution receives its Action instance."""
        return self.action_expression is not None

    @property
    def execution_needs_guarantees(self) -> bool:
        """Whether the triggered execution receives guarantee continuations."""
        return self.child_guarantees_name is not None


@dataclass
class ChildGuaranteesContext:
    """A guarantee bundle for one direct Action Execution."""

    name: str
    class_reference: naming.ClassReference


@dataclass
class GuaranteeRegistrationContext:
    """One generated task registration for a consumed guarantee."""

    child_guarantees_names: list[str]
    guarantee_name: str
    method_name: str


@dataclass
class DestructionConnectionGuaranteeRegistrationContext:
    """A destruction continuation's dependency on one Guarantee."""

    child_guarantees_name: str
    guarantee_name: str


@dataclass
class GuaranteesContext:
    """Generated guarantees for one action execution."""

    class_name: str
    child_guarantees: list[ChildGuaranteesContext]
    publications: list[str]
    registrations: Sequence[GuaranteeRegistrationContext]


@dataclass
class CalleeBindingJoinContext:
    """The generated join for one direct callee binding."""

    triggered_action_execution_name: str
    callee_binding_hole_method_name: str
    method_name: str
    dependency_count: int
    destruction_positions: list[DestructionPositionContext]


@dataclass
class BindingHoleFanoutContext:
    """A generated method that notifies every consumer of one Binding Hole."""

    binding_hole_method_name: str
    fragment_method_names: list[str]
    callee_binding_join_method_names: list[str]
    destructor_executions: list[TriggeredActionExecutionContext]


@dataclass
class TriggerForDestroyedCalleeGuaranteeParticleContext:
    """One Action Execution for a destroyed callee-guaranteed particle."""

    method_name: str
    action_execution: TriggeredActionExecutionContext
    callee_binding_join_method_names: list[str]


@dataclass
class ActionExecutionContext:
    """Template context for operation-graph execution of one action."""

    execution_class_name: str
    local_position_statements: list[ActionStatementContext]
    fragments: list[ActionFragmentContext]
    binding_hole_fanouts: list[BindingHoleFanoutContext]
    action_executions: list[TriggeredActionExecutionContext]
    triggers_for_destroyed_callee_guarantee_particles: list[
        TriggerForDestroyedCalleeGuaranteeParticleContext
    ]
    callee_binding_joins: list[CalleeBindingJoinContext]
    guarantees: GuaranteesContext | None
    accepts_destruction_connections: bool
    trace_operations: bool = False
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
        self.needs_action = any(
            triggered_action.action_expression is not None
            and triggered_action.action_expression.local_position_member_name is None
            for triggered_action in self.action_executions
        )

    @property
    def needs_tracing(self) -> bool:
        """Whether generated code imports the tracing runtime."""
        if not self.trace_operations:
            return False
        return any(
            action_execution.created_destruction_connections
            for action_execution in self.action_executions
        )

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
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.constraints)
        class_references.extend(self.implied_qualities)
        return sorted(
            {class_reference.module_name for class_reference in class_references}
        )
