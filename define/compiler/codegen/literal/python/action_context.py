"""Action context for literal Python code generation."""

from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from define.compiler.codegen.literal.python import naming, template_context
    from define.compiler.validator.reference_graph import operation_graph_model


class ActionRole(enum.Enum):
    """The runtime role of one generated action definition."""

    ACTION = enum.auto()
    ENTRY_POINT = enum.auto()

    @property
    def has_execute_method(self) -> bool:
        """Whether the runtime invokes this action through execute()."""
        return self is ActionRole.ENTRY_POINT


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    module_name: str
    execution: template_context.ActionExecutionContext
    execute_method_names: list[str]
    role: ActionRole
    interface_positions: list[template_context.InterfacePositionContext]
    implied_qualities: list[naming.ClassReference]
    trace_operations: bool = False
    trace_action_name: str | None = None

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.implied_qualities)

    @property
    def imports(self) -> list[str]:
        """External modules imported by this definition."""
        class_references: list[naming.ClassReference] = []
        class_references.extend(self.implied_qualities)
        for interface_position in self.interface_positions:
            class_references.extend(interface_position.constraints)
        for statement in self.execution.local_position_statements:
            class_references.extend(statement.constraints)
        for fragment in self.execution.fragments:
            for statement in fragment.statements:
                position = typing.cast(
                    "template_context.PositionExpr", statement.position
                )
                class_references.extend(position.class_references)
                if statement.to_position is not None:
                    class_references.extend(statement.to_position.class_references)
        for action_execution in self.execution.action_executions:
            class_references.extend(
                connection.destruction_continuation.execution_class
                for connection in action_execution.created_destruction_connections
            )
            if action_execution.action is not None:
                class_references.extend(action_execution.action.class_references)
            class_references.append(action_execution.execution_class)
        for callee_binding_join in self.execution.callee_binding_joins:
            for destruction_position in callee_binding_join.destruction_positions:
                class_references.extend(destruction_position.position.class_references)
        return sorted(
            {class_reference.module_name for class_reference in class_references}
        )


@dataclass(frozen=True, slots=True)
class ChildGuarantees:
    """A generated child's guarantee interface and its member in the caller."""

    member_name: str
    callee_interface: GuaranteeInterface


@dataclass(frozen=True, slots=True)
class GuaranteeInterface:
    """Generated guarantee members exposed across one action boundary."""

    class_reference: naming.ClassReference
    child_guarantees: dict[operation_graph_model.ActionExecution, ChildGuarantees]
    # Guarantee paths end at the Position Operation that publishes the
    # guarantee; its value here is the generated task-list member name.
    guarantee_names_by_operation: dict[operation_graph_model.PositionOperationNode, str]


@dataclass(frozen=True, slots=True)
class GeneratedAction:
    """Generated context and caller-facing interface of one action."""

    context: ActionDefinitionContext
    binding_hole_method_names: dict[operation_graph_model.BindingHole, str]
    guarantee_interface: GuaranteeInterface | None
    destruction_continuations: dict[
        operation_graph_model.DestructionFactDestroyNode,
        template_context.DestructionContinuationContext,
    ]
