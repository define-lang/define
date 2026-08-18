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
    triggered_action_execution,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_model,
)


@dataclass(frozen=True, slots=True)
class GeneratedExecution:
    """Generated execution context and caller-facing interface."""

    context: template_context.ActionExecutionContext
    input_method_names: dict[operation_graph_model.BindingHole, str]
    guarantee_interface: action_context.GuaranteeInterface | None
    execute_method_names: list[str]
    destruction_continuations: dict[
        operation_graph_model.DestructionFactDestroyNode,
        template_context.DestructionContinuationContext,
    ]


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
        statement_generator = action_statements.ActionStatementsGenerator(
            self._definition,
            self._converter,
            names.local_positions,
            names.destruction_positions,
            self._plan.destruction_connection_by_operation,
            names.destruction_connections,
            self._operation_labels,
        )
        local_position_statements = statement_generator.build_local_positions()
        guarantees = action_guarantees.ActionGuaranteesGenerator(
            self._definition,
            self._converter,
            self._plan,
            self._generated_actions,
            names,
        ).generate()
        action_execution_contexts = (
            triggered_action_execution.TriggeredActionExecutionGenerator(
                self._definition,
                self._converter,
                self._generated_actions,
                self._plan,
                self._operation_labels,
                names,
                guarantees.interface,
                statement_generator,
            ).generate()
        )
        triggered_action_input_contexts = self._generate_triggered_action_inputs(
            names,
            statement_generator,
        )
        triggers_for_destroyed_callee_guarantee_particle_contexts = (
            self._generate_triggers_for_destroyed_callee_guarantee_particles(names)
        )
        destruction_continuations = self._generate_destruction_continuations(names)
        context = template_context.ActionExecutionContext(
            execution_class_name=self._converter.execution_class_name(
                self._definition.typed_name.name_content.path.relative_path
            ),
            local_position_statements=local_position_statements,
            fragments=self._generate_fragments(
                names,
                statement_generator,
            ),
            caller_inputs=self._generate_caller_inputs(names),
            action_executions=action_execution_contexts,
            triggers_for_destroyed_callee_guarantee_particles=(
                triggers_for_destroyed_callee_guarantee_particle_contexts
            ),
            triggered_action_inputs=triggered_action_input_contexts,
            guarantees=guarantees.context,
            accepts_destruction_connections=(
                self._plan.accepts_destruction_connections
            ),
            trace_operations=self._operation_labels is not None,
        )
        return GeneratedExecution(
            context=context,
            input_method_names=names.caller_inputs,
            guarantee_interface=guarantees.interface,
            execute_method_names=[
                names.fragments[fragment] for fragment in self._plan.execute_fragments
            ],
            destruction_continuations=destruction_continuations,
        )

    def _generate_destruction_continuations(
        self,
        names: action_names.ActionNames,
    ) -> dict[
        operation_graph_model.DestructionFactDestroyNode,
        template_context.DestructionContinuationContext,
    ]:
        destruction_continuations: dict[
            operation_graph_model.DestructionFactDestroyNode,
            template_context.DestructionContinuationContext,
        ] = {}
        for fragment in self._plan.fragments:
            if not isinstance(fragment, action_plan.DestructionActionFragment):
                continue
            operation = fragment.destruction_operation
            destruction_continuations[operation] = (
                template_context.DestructionContinuationContext(
                    execution_class=self._converter.execution_class_reference(
                        self._definition.typed_name
                    ),
                    member_name=names.continue_destroy_methods[fragment],
                )
            )
        return destruction_continuations

    def _generate_fragments(
        self,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
    ) -> list[template_context.ActionFragmentContext]:
        fragments: list[template_context.ActionFragmentContext] = []
        for fragment in self._plan.fragments:
            destruction_connection_names_to_complete: list[str] = []
            for connection in fragment.destruction_connections_to_complete:
                destruction_connection_names_to_complete.append(
                    names.destruction_connections[connection]
                )
            guarantee_publication_names: list[str] = []
            for publication in fragment.guarantee_publications:
                guarantee_publication_names.append(
                    names.guarantee_publications[publication]
                )
            fragments.append(
                template_context.ActionFragmentContext(
                    method_name=names.fragments[fragment],
                    statements=[
                        statement_generator.build_operation(operation)
                        for operation in fragment.operations
                    ],
                    successor_fragment_method_names=[
                        names.fragments[successor]
                        for successor in fragment.successor_fragments
                    ],
                    triggered_input_successor_method_names=[
                        names.triggered_inputs[triggered_input]
                        for triggered_input in (
                            fragment.callee_binding_joins_that_depend_on_fragment
                        )
                    ],
                    triggered_action_successor_init_method_names=[
                        names.triggered_actions[action_execution].initializer_name
                        for action_execution in fragment.action_execution_successors
                    ],
                    execution_input_successor_method_names=[
                        names.triggered_inputs[triggered_input]
                        for triggered_input in (
                            fragment.triggered_action_execution_callee_binding_joins
                        )
                    ],
                    guarantee_publication_names=guarantee_publication_names,
                    dependency_count=fragment.dependency_count,
                    continue_destroy_method_name=names.continue_destroy_methods.get(
                        fragment
                    ),
                    destruction_connection_names_to_complete=(
                        destruction_connection_names_to_complete
                    ),
                )
            )
        return fragments

    def _generate_caller_inputs(
        self, names: action_names.ActionNames
    ) -> list[template_context.CallerDependencyFanoutContext]:
        return [
            template_context.CallerDependencyFanoutContext(
                input_method_name=names.caller_inputs[caller_input.binding_hole],
                fragment_method_names=[
                    names.fragments[fragment] for fragment in caller_input.fragments
                ],
                triggered_input_method_names=[
                    names.triggered_inputs[triggered_input]
                    for triggered_input in caller_input.callee_binding_joins
                ],
                destructor_execution_init_methods=[
                    names.triggered_actions[destructor_execution].initializer_name
                    for destructor_execution in caller_input.destructor_executions
                ],
            )
            for caller_input in self._plan.binding_hole_fanouts
        ]

    def _generate_triggered_action_inputs(
        self,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
    ) -> list[template_context.CalleeDependencyJoinContext]:
        triggered_action_inputs: list[template_context.CalleeDependencyJoinContext] = []
        for triggered_input in self._plan.callee_binding_joins:
            execution = triggered_input.execution
            triggered_action_inputs.append(
                template_context.CalleeDependencyJoinContext(
                    triggered_action_execution_name=(
                        names.triggered_actions[execution].execution_name
                    ),
                    callee_input_method_name=self._generated_actions[
                        execution.callee_action_name
                    ].input_method_names[triggered_input.callee_binding_hole],
                    method_name=names.triggered_inputs[triggered_input],
                    dependency_count=triggered_input.dependency_count,
                    destruction_positions=[
                        template_context.DestructionPositionContext(
                            member_name=names.destruction_positions[operation],
                            position=statement_generator.build_position(
                                operation.target
                            ),
                        )
                        for operation in triggered_input.contributed_destruction_operations
                    ],
                )
            )
        return triggered_action_inputs

    def _generate_triggers_for_destroyed_callee_guarantee_particles(
        self,
        names: action_names.ActionNames,
    ) -> list[template_context.TriggerForDestroyedCalleeGuaranteeParticleContext]:
        contexts: list[
            template_context.TriggerForDestroyedCalleeGuaranteeParticleContext
        ] = []
        for (
            trigger_for_destroyed_callee_guarantee_particle
        ) in self._plan.triggers_for_destroyed_callee_guarantee_particles:
            triggered_action_names = names.triggered_actions[
                trigger_for_destroyed_callee_guarantee_particle.execution
            ]
            triggered_input_method_names: list[str] = []
            for (
                triggered_input
            ) in trigger_for_destroyed_callee_guarantee_particle.callee_binding_joins:
                triggered_input_method_names.append(
                    names.triggered_inputs[triggered_input]
                )
            contexts.append(
                template_context.TriggerForDestroyedCalleeGuaranteeParticleContext(
                    method_name=triggered_action_names.canonical_name,
                    action_execution_init_method_name=(
                        triggered_action_names.initializer_name
                    ),
                    triggered_input_method_names=triggered_input_method_names,
                )
            )
        return contexts
