"""Literal Python lowering for Action Executions."""

import typing

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_names,
    action_statements,
    naming,
    template_context,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import operation_graph_labeler


@typing.final
class TriggeredActionExecutionGenerator:
    """Lower direct Action Executions for one generated execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedAction
        ],
        plan: action_plan.ActionPlan,
        operation_labels: operation_graph_labeler.OperationGraphLabeler | None,
        names: action_names.ActionNames,
        guarantee_interface: action_context.GuaranteeInterface | None,
        statement_generator: action_statements.ActionStatementsGenerator,
    ):
        """Initialize Action Execution lowering for one action plan."""
        self._definition = definition
        self._converter = converter
        self._generated_actions = generated_actions
        self._plan = plan
        self._operation_labels = operation_labels
        self._names = names
        self._guarantee_interface = guarantee_interface
        self._statement_generator = statement_generator

    def generate(self) -> list[template_context.TriggeredActionExecutionContext]:
        """Generate direct Action Execution contexts."""
        action_executions: list[template_context.TriggeredActionExecutionContext] = []
        for planned_execution in self._plan.action_executions:
            execution = planned_execution.execution
            action_execution_names = self._names.triggered_actions[execution]
            generated_callee = self._generated_actions[execution.callee_action_name]
            destruction_connections = planned_execution.created_destruction_connections
            created_destruction_connections = (
                self._generate_created_destruction_connections(destruction_connections)
            )
            destruction_connections_member_name = None
            if destruction_connections:
                destruction_connections_member_name = (
                    self._names.triggered_destruction_connections[execution]
                )
            elif planned_execution.forwards_destruction_connections:
                destruction_connections_member_name = "destruction_connections"
            action = None
            if generated_callee.context.execution.needs_action:
                action = self._statement_generator.build_action(execution.callee)
            child_guarantees_name = None
            if self._guarantee_interface is not None:
                child_guarantees = self._guarantee_interface.child_guarantees.get(
                    execution
                )
                if child_guarantees is not None:
                    child_guarantees_name = child_guarantees.member_name
            action_executions.append(
                template_context.TriggeredActionExecutionContext(
                    action=action,
                    execution_class=self._converter.execution_class_reference(
                        execution.callee_action_name
                    ),
                    init_method_name=action_execution_names.initializer_name,
                    execution_name=action_execution_names.execution_name,
                    child_guarantees_name=child_guarantees_name,
                    created_destruction_connections=created_destruction_connections,
                    destruction_connections_member_name=(
                        destruction_connections_member_name
                    ),
                    forwards_destruction_connections=(
                        planned_execution.forwards_destruction_connections
                    ),
                    trace_action_name=(
                        self._operation_labels.triggered_action_execution_name(
                            self._definition.typed_name,
                            execution,
                        ).local_name
                        if self._operation_labels is not None
                        else None
                    ),
                )
            )
        return action_executions

    def _generate_created_destruction_connections(
        self,
        destruction_connections: list[action_plan.DestructionConnection],
    ) -> list[template_context.DestructionConnectionContext]:
        contexts: list[template_context.DestructionConnectionContext] = []
        for connection in destruction_connections:
            callee_destroy = connection.callee_destroy
            destruction_continuation = self._generated_actions[
                callee_destroy.action
            ].destruction_continuations[callee_destroy.operation]
            contexts.append(
                template_context.DestructionConnectionContext(
                    member_name=self._names.destruction_connections[connection],
                    destruction_continuation=destruction_continuation,
                    start_method_names=[
                        self._names.fragments[fragment]
                        for fragment in connection.first_fragments_of_destructions
                    ],
                    expected_completions=len(connection.completion_fragments),
                )
            )
        return contexts
