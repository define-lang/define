"""Literal Python execution lowering for action definitions."""

import typing
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_guarantees,
    action_names,
    action_statements,
    naming,
    template_context,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph_action_resolver,
    operation_graph_labeler,
)


@dataclass(frozen=True, slots=True)
class GeneratedExecution:
    """Generated execution context and caller-facing interface."""

    context: template_context.ActionExecutionContext
    input_method_names: dict[operation_graph_action_resolver.ResolvedCallerInput, str]
    guarantee_interface: action_context.GuaranteeInterface | None


@typing.final
class ActionExecutionGenerator:
    """Lower one action plan to a literal Python execution context."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedAction
        ],
        plan: action_plan.ActionPlan,
        operation_labels: operation_graph_labeler.OperationGraphLabeler | None,
    ):
        """Initialize execution lowering with its action and generated callees.

        ``operation_labels`` is present for traced generation and absent for
        ordinary generation.
        """
        self._definition = definition
        self._converter = converter
        self._generated_actions = generated_actions
        self._plan = plan
        self._operation_labels = operation_labels

    def generate(self) -> GeneratedExecution:
        """Generate the execution context and caller-facing interface."""
        names = action_names.ActionNameGenerator(
            self._definition,
            self._plan,
            self._generated_actions,
        ).generate()
        block_generator = action_statements.ActionStatementsGenerator(
            self._definition,
            self._converter,
            names.local_positions,
            self._operation_labels,
        )
        local_position_statements = block_generator.build_local_positions()
        guarantees = action_guarantees.ActionGuaranteesGenerator(
            self._definition,
            self._converter,
            self._plan,
            self._generated_actions,
            names,
        ).generate()
        triggered_actions = self._generate_triggered_actions(
            names, guarantees.interface, block_generator
        )
        context = template_context.ActionExecutionContext(
            execution_class_name=self._converter.execution_class_name(
                self._definition.typed_name.name_content.path.relative_path
            ),
            local_position_statements=local_position_statements,
            fragments=self._generate_fragments(
                names, guarantees.interface, block_generator
            ),
            execute_fragment_method_names=[
                names.fragments[fragment] for fragment in self._plan.execute_fragments
            ],
            caller_inputs=self._generate_caller_inputs(names),
            triggered_actions=triggered_actions,
            triggered_action_inputs=self._generate_triggered_inputs(names),
            guarantee_destructor_triggers=(
                self._generate_guarantee_destructor_triggers(names)
            ),
            guarantee_registrations=guarantees.guarantee_registrations,
            guarantees=guarantees.context,
            trace_operations=self._operation_labels is not None,
        )
        return GeneratedExecution(
            context,
            names.caller_inputs,
            guarantees.interface,
        )

    def _generate_fragments(
        self,
        names: action_names.ActionNames,
        guarantee_interface: action_context.GuaranteeInterface | None,
        block_generator: action_statements.ActionStatementsGenerator,
    ) -> list[template_context.ActionFragmentContext]:
        guarantee_names_by_operation = (
            guarantee_interface.guarantee_names_by_operation
            if guarantee_interface is not None
            else {}
        )
        fragments: list[template_context.ActionFragmentContext] = []
        for fragment in self._plan.fragments:
            fragments.append(
                template_context.ActionFragmentContext(
                    method_name=names.fragments[fragment],
                    statements=[
                        block_generator.build_operation(operation)
                        for operation in fragment.operations
                    ],
                    successor_fragment_method_names=[
                        names.fragments[successor]
                        for successor in fragment.successor_fragments
                    ],
                    triggered_input_successor_method_names=[
                        names.triggered_inputs[triggered_input]
                        for triggered_input in fragment.triggered_input_successors
                    ],
                    triggered_action_successor_init_method_names=[
                        names.triggered_actions[action_trigger].initializer_name
                        for action_trigger in fragment.triggered_action_successors
                    ],
                    execution_input_successor_method_names=[
                        names.triggered_inputs[triggered_input]
                        for triggered_input in fragment.execution_input_successors
                    ],
                    guarantee_publication_names=[
                        guarantee_names_by_operation[publication.operation]
                        for publication in fragment.guarantee_publications
                    ],
                    dependency_count=fragment.dependency_count,
                )
            )
        return fragments

    def _generate_triggered_actions(
        self,
        names: action_names.ActionNames,
        guarantee_interface: action_context.GuaranteeInterface | None,
        block_generator: action_statements.ActionStatementsGenerator,
    ) -> list[template_context.TriggeredActionContext]:
        triggered_actions: list[template_context.TriggeredActionContext] = []
        for trigger in self._plan.action_triggers:
            action_trigger_names = names.triggered_actions[trigger]
            generated_callee = self._generated_actions[trigger.callee_action_name]
            action = None
            if generated_callee.context.execution.needs_action:
                action = block_generator.build_action(trigger.callee)
            child_guarantees_name = None
            if guarantee_interface is not None:
                child_guarantees = guarantee_interface.child_guarantees.get(trigger)
                if child_guarantees is not None:
                    child_guarantees_name = child_guarantees.member_name
            triggered_actions.append(
                template_context.TriggeredActionContext(
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
        return triggered_actions

    def _generate_triggered_inputs(
        self,
        names: action_names.ActionNames,
    ) -> list[template_context.TriggeredActionInputContext]:
        triggered_action_inputs: list[template_context.TriggeredActionInputContext] = []
        for triggered_input in self._plan.triggered_action_inputs:
            trigger = triggered_input.action_trigger
            triggered_action_inputs.append(
                template_context.TriggeredActionInputContext(
                    triggered_action_execution_name=(
                        names.triggered_actions[
                            triggered_input.action_trigger
                        ].execution_name
                    ),
                    callee_input_method_name=self._generated_actions[
                        trigger.callee_action_name
                    ].input_method_names[triggered_input.callee_input],
                    method_name=names.triggered_inputs[triggered_input],
                    dependency_count=triggered_input.dependency_count,
                )
            )
        return triggered_action_inputs

    def _generate_caller_inputs(
        self, names: action_names.ActionNames
    ) -> list[template_context.CallerInputContext]:
        return [
            template_context.CallerInputContext(
                input_method_name=names.caller_inputs[caller_input.resolved_input],
                fragment_method_names=[
                    names.fragments[fragment] for fragment in caller_input.fragments
                ],
                triggered_input_method_names=[
                    names.triggered_inputs[triggered_input]
                    for triggered_input in caller_input.triggered_inputs
                ],
                destructor_execution_init_methods=[
                    names.triggered_actions[destructor_trigger].initializer_name
                    for destructor_trigger in caller_input.destructor_triggers
                ],
            )
            for caller_input in self._plan.caller_inputs
        ]

    def _generate_guarantee_destructor_triggers(
        self,
        names: action_names.ActionNames,
    ) -> list[template_context.GuaranteeDestructorTriggerContext]:
        return [
            template_context.GuaranteeDestructorTriggerContext(
                method_name=names.guarantee_destructor_triggers[destructor_trigger],
                destructor_execution_init_method=names.triggered_actions[
                    destructor_trigger.action_trigger
                ].initializer_name,
                triggered_input_method_names=[
                    names.triggered_inputs[triggered_input]
                    for triggered_input in destructor_trigger.triggered_inputs
                ],
            )
            for destructor_trigger in self._plan.guarantee_destructor_triggers
        ]
