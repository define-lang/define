"""Action context for literal Python code generation."""

from __future__ import annotations

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler.codegen import action_plan
    from define.compiler.codegen.literal.python import naming, template_context
    from define.compiler.validator.reference_graph import operation_graph_model


@dataclass
class ActionDefinitionContext:
    """Template context for rendering an action definition class."""

    class_name: str
    module_name: str
    execution: template_context.ActionExecutionContext
    is_entry_point: bool
    interface_positions: list[template_context.InterfacePositionContext]
    implied_qualities: list[naming.ClassReference]
    view_point_create_method_names: list[str]
    view_point_create_join_assignments: list[
        template_context.CalleeJoinAssignmentContext
    ]
    trace_operations: bool = False
    trace_action_name: str | None = None

    @property
    def needs_classvar(self) -> bool:
        """Whether the generated class has class variables."""
        return bool(self.implied_qualities)

    @property
    def imports(self) -> list[str]:
        """External modules imported by this definition."""
        module_names = {
            class_reference.module_name for class_reference in self.implied_qualities
        }
        module_names.update(self._position_constraint_module_names())
        module_names.update(self._fragment_module_names())
        module_names.update(self._action_execution_module_names())
        module_names.update(self._destruction_position_module_names())
        return sorted(module_names)

    def _position_constraint_module_names(self) -> Iterator[str]:
        for interface_position in self.interface_positions:
            for class_reference in interface_position.constraints:
                yield class_reference.module_name
        for statement in self.execution.local_position_statements:
            for class_reference in statement.constraints:
                yield class_reference.module_name

    def _fragment_module_names(self) -> Iterator[str]:
        for fragment in self.execution.fragments:
            for statement in fragment.statements:
                position = typing.cast(
                    "template_context.PositionExpr", statement.position
                )
                yield from position.referenced_module_names()
                if statement.to_position is not None:
                    yield from statement.to_position.referenced_module_names()
            if fragment.guarantee_dependent_destroy_position is not None:
                yield from (
                    fragment.guarantee_dependent_destroy_position.position.referenced_module_names()
                )

    def _action_execution_module_names(self) -> Iterator[str]:
        for action_execution in self.execution.action_executions:
            for connection in action_execution.created_destruction_connections:
                yield connection.destruction_continuation.execution_class.module_name
                for destructor in connection.destruction_contract_destructors:
                    yield destructor.execution_class.module_name
            action_expression = action_execution.action_expression
            if action_expression is not None:
                yield from action_expression.referenced_module_names()
            yield action_execution.execution_class.module_name

    def _destruction_position_module_names(self) -> Iterator[str]:
        for destruction_position in self.execution.destruction_positions:
            yield from destruction_position.position.referenced_module_names()
        for callee_binding_plan in self.execution.callee_binding_plans:
            for destruction_position in callee_binding_plan.destruction_positions:
                yield from destruction_position.position.referenced_module_names()


@dataclass(frozen=True, slots=True)
class GeneratedActionDefinition:
    """Generated action-definition context and caller-facing interface."""

    context: ActionDefinitionContext
    action_interface: GeneratedActionInterface


@dataclass(slots=True)
class GeneratedBindingHoleNames:
    """Generated names through which callers use one Binding Hole."""

    base_name: str
    method_name: str
    separate_init_method_name: str | None = None
    continuation_method_name: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratedActionInterface:
    """Caller-facing interface of one generated action."""

    needs_action: bool
    binding_holes: dict[
        operation_graph_model.BindingHole,
        GeneratedBindingHoleNames,
    ]
    guarantee_names_by_operation: dict[operation_graph_model.PositionOperationNode, str]
    execution_member_names: dict[operation_graph_model.ActionExecution, str]
    join_member_names: dict[action_plan.JoinTarget, str]
    fragment_method_names: dict[action_plan.ActionFragment, str]
    destruction_continuations: dict[
        operation_graph_model.DestructionFactDestroyNode,
        template_context.DestructionContinuationContext,
    ]


@dataclass(frozen=True, slots=True)
class GeneratedExecution:
    """Generated execution context and caller-facing action interface."""

    context: template_context.ActionExecutionContext
    action_interface: GeneratedActionInterface
