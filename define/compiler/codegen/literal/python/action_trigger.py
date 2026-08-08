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

    def generate(self) -> template_context.ActionTriggersContext:
        """Generate the template context for direct Action Triggers."""
        return template_context.ActionTriggersContext(
            action_triggers=self._generate_action_triggers(),
            triggered_action_inputs=self._generate_triggered_inputs(),
            guarantee_destructor_triggers=(
                self._generate_guarantee_destructor_triggers()
            ),
        )

    def _generate_action_triggers(
        self,
    ) -> list[template_context.ActionTriggerContext]:
        action_triggers: list[template_context.ActionTriggerContext] = []
        for trigger in self._plan.action_triggers:
            action_trigger_names = self._names.triggered_actions[trigger]
            generated_callee = self._generated_actions[trigger.callee_action_name]
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

    def _generate_triggered_inputs(
        self,
    ) -> list[template_context.TriggeredActionInputContext]:
        triggered_action_inputs: list[template_context.TriggeredActionInputContext] = []
        for triggered_input in self._plan.triggered_action_inputs:
            trigger = triggered_input.action_trigger
            triggered_action_inputs.append(
                template_context.TriggeredActionInputContext(
                    triggered_action_execution_name=(
                        self._names.triggered_actions[trigger].execution_name
                    ),
                    callee_input_method_name=self._generated_actions[
                        trigger.callee_action_name
                    ].input_method_names[triggered_input.callee_input],
                    method_name=self._names.triggered_inputs[triggered_input],
                    dependency_count=triggered_input.dependency_count,
                )
            )
        return triggered_action_inputs

    def _generate_guarantee_destructor_triggers(
        self,
    ) -> list[template_context.GuaranteeDestructorTriggerContext]:
        return [
            template_context.GuaranteeDestructorTriggerContext(
                method_name=self._names.guarantee_destructor_triggers[
                    destructor_trigger
                ],
                destructor_execution_init_method=self._names.triggered_actions[
                    destructor_trigger.action_trigger
                ].initializer_name,
                triggered_input_method_names=[
                    self._names.triggered_inputs[triggered_input]
                    for triggered_input in destructor_trigger.triggered_inputs
                ],
            )
            for destructor_trigger in self._plan.guarantee_destructor_triggers
        ]
