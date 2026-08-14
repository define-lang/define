"""Literal Python lowering for Action Triggers."""

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
class ActionTriggerGenerator:
    """Lower direct Action Triggers for one generated execution."""

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
        """Initialize Action Trigger lowering for one action plan."""
        self._definition = definition
        self._converter = converter
        self._generated_actions = generated_actions
        self._plan = plan
        self._operation_labels = operation_labels
        self._names = names
        self._guarantee_interface = guarantee_interface
        self._statement_generator = statement_generator

    def generate(self) -> list[template_context.ActionTriggerContext]:
        """Generate direct Action Trigger contexts."""
        action_triggers: list[template_context.ActionTriggerContext] = []
        for planned_trigger in self._plan.action_triggers:
            trigger = planned_trigger.action_trigger
            action_trigger_names = self._names.triggered_actions[trigger]
            generated_callee = self._generated_actions[trigger.callee_action_name]
            destruction_connections = planned_trigger.created_destruction_connections
            created_destruction_connections = (
                self._generate_created_destruction_connections(destruction_connections)
            )
            destruction_connections_member_name = None
            if destruction_connections:
                destruction_connections_member_name = (
                    self._names.triggered_destruction_connections[trigger]
                )
            elif planned_trigger.forwards_destruction_connections:
                destruction_connections_member_name = "destruction_connections"
            action = None
            if generated_callee.context.execution.needs_action:
                action = self._statement_generator.build_action(trigger.callee)
            child_guarantees_name = None
            if self._guarantee_interface is not None:
                child_guarantees = self._guarantee_interface.child_guarantees.get(
                    trigger
                )
                if child_guarantees is not None:
                    child_guarantees_name = child_guarantees.member_name
            action_triggers.append(
                template_context.ActionTriggerContext(
                    action=action,
                    execution_class=self._converter.execution_class_reference(
                        trigger.callee_action_name
                    ),
                    init_method_name=action_trigger_names.initializer_name,
                    execution_name=action_trigger_names.execution_name,
                    child_guarantees_name=child_guarantees_name,
                    created_destruction_connections=created_destruction_connections,
                    destruction_connections_member_name=(
                        destruction_connections_member_name
                    ),
                    forwards_destruction_connections=(
                        planned_trigger.forwards_destruction_connections
                    ),
                    trace_action_name=(
                        self._operation_labels.triggered_action_execution_name(
                            self._definition.typed_name,
                            trigger,
                        ).local_name
                        if self._operation_labels is not None
                        else None
                    ),
                )
            )
        return action_triggers

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
