"""Literal Python lowering for Action Executions."""

from __future__ import annotations

import typing

from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_guarantees,
    action_names,
    action_statements,
    naming,
    template_context,
)

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from define.compiler import ast
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator.reference_graph import (
        operation_graph_labeler,
        operation_graph_model,
    )


@typing.final
class TriggeredActionExecutionGenerator:
    """Lower direct Action Executions for one generated execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedActionInterface
        ],
        plan: action_plan.ActionPlan,
        operation_labels: operation_graph_labeler.OperationGraphLabeler | None,
        names: action_names.ActionNames,
        guarantee_consumptions: action_guarantees.GeneratedGuaranteeConsumptions | None,
        statement_generator: action_statements.ActionStatementsGenerator,
    ):
        """Initialize Action Execution lowering for one action plan."""
        self._definition = definition
        self._converter = converter
        self._generated_actions = generated_actions
        self._plan = plan
        self._operation_labels = operation_labels
        self._names = names
        self._guarantee_consumptions = guarantee_consumptions
        self._statement_generator = statement_generator

    def generate(
        self,
    ) -> dict[
        operation_graph_model.ActionExecution,
        template_context.TriggeredActionExecutionContext,
    ]:
        """Generate direct Action Execution contexts."""
        action_executions: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ] = {}
        for planned_execution in self._plan.action_executions.values():
            execution = planned_execution.execution
            action_execution_names = self._names.action_executions[execution]
            generated_callee = self._generated_actions[execution.callee_action_name]
            destruction_connections = planned_execution.created_destruction_connections
            created_destruction_connections = (
                self._generate_created_destruction_connections(destruction_connections)
            )
            guarantee_consumptions: Sequence[
                template_context.GuaranteeConsumptionContext
            ] = ()
            if self._guarantee_consumptions is not None:
                guarantee_consumptions = (
                    self._guarantee_consumptions.consumptions_by_action_execution.get(
                        execution, ()
                    )
                )
            action_expression = None
            if generated_callee.needs_action:
                action_expression = self._statement_generator.build_action(
                    execution.callee
                )
            trace_parent_action_name = None
            if isinstance(
                planned_execution,
                action_plan.ContributedDestructorActionExecutionPlan,
            ):
                trace_parent_action_name = self._trace_action_name(
                    planned_execution.destroying_action_execution
                )
            callee_join_assignments = self._generate_callee_join_assignments(
                planned_execution.callee_join_assignments,
            )
            action_executions[execution] = (
                template_context.TriggeredActionExecutionContext(
                    action_expression=action_expression,
                    execution_class=self._converter.execution_class_reference(
                        execution.callee_action_name
                    ),
                    execution_name=action_execution_names.execution_name,
                    callee_join_assignments=callee_join_assignments,
                    guarantee_consumptions=guarantee_consumptions,
                    created_destruction_connections=created_destruction_connections,
                    forwards_destruction_connections=(
                        planned_execution.forwards_destruction_connections
                    ),
                    trace_parent_action_name=trace_parent_action_name,
                    trace_action_name=self._trace_action_name(execution),
                )
            )
        return action_executions

    def _generate_destruction_contract_destructors(
        self,
        connection: action_plan.DestructionConnection,
    ) -> list[template_context.DestructionContractDestructorExecutionContext]:
        """Generate Destructor Action Executions contributed by the caller."""
        contexts: list[
            template_context.DestructionContractDestructorExecutionContext
        ] = []
        for destructor in connection.destruction_contract_destructors:
            execution = destructor.execution
            generated_destructor = self._generated_actions[execution.callee_action_name]
            guarantee_names_completing_connection: list[str] = []
            for guarantee in destructor.guarantees_preceding_callee_destroy:
                guarantee_names_completing_connection.append(
                    generated_destructor.guarantee_names_by_operation[
                        guarantee.operation
                    ]
                )
            contexts.append(
                template_context.DestructionContractDestructorExecutionContext(
                    execution_class=self._converter.execution_class_reference(
                        execution.callee_action_name
                    ),
                    run_method_name=(
                        self._names.destruction_contract_destructor_run_method_names[
                            destructor
                        ]
                    ),
                    action_parent_binding_method_name=(
                        generated_destructor.binding_holes[
                            destructor.action_parent_binding_hole
                        ].method_name
                    ),
                    guarantee_names_completing_connection=(
                        guarantee_names_completing_connection
                    ),
                    trace_action_name=self._trace_action_name(execution),
                )
            )
        return contexts

    def _generate_callee_join_assignments(
        self,
        assignments: Sequence[action_plan.CalleeJoinAssignment],
    ) -> list[template_context.CalleeJoinAssignmentContext]:
        contexts: list[template_context.CalleeJoinAssignmentContext] = []
        for assignment in assignments:
            execution_member_names, generated_callee = (
                self._names.nested_generated_execution_path(
                    assignment.execution_path,
                )
            )
            contexts.append(
                template_context.CalleeJoinAssignmentContext(
                    member_name=generated_callee.join_member_names[assignment.target],
                    dependency_count=assignment.dependency_count,
                    execution_member_names=execution_member_names,
                )
            )
        return contexts

    def _trace_action_name(
        self,
        execution: operation_graph_model.ActionExecution,
    ) -> str | None:
        if self._operation_labels is None:
            return None
        return self._operation_labels.triggered_action_execution_name(
            self._definition.typed_name,
            execution,
        ).local_name

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
            # TODO: Preserve each connected task's Particle Operation dependencies
            # through codegen. Starting all of them when execution reaches the
            # callee Destroy adds dependencies absent from the Particle Operation
            # dependency graph.
            destruction_contract_destructors = (
                self._generate_destruction_contract_destructors(connection)
            )
            contexts.append(
                template_context.DestructionConnectionContext(
                    member_name=self._names.destruction_connections[connection],
                    destruction_continuation=destruction_continuation,
                    start_method_names=(
                        self._names.destruction_connection_continuation_method_names(
                            connection.continuations
                        )
                    ),
                    destruction_contract_destructors=destruction_contract_destructors,
                    predecessor_count=connection.predecessor_count,
                )
            )
        return contexts
