"""Literal Python execution lowering for action definitions."""

from __future__ import annotations

import typing
from dataclasses import dataclass

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

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator.reference_graph import (
        operation_graph_labeler,
        operation_graph_model,
    )


@dataclass(frozen=True, slots=True)
class GeneratedExecution:
    """Generated execution context and caller-facing interface."""

    context: template_context.ActionExecutionContext
    binding_hole_method_names: dict[operation_graph_model.BindingHole, str]
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
        action_execution_contexts_by_execution = (
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
        callee_binding_join_contexts = self._generate_callee_binding_joins(
            names,
            statement_generator,
        )
        triggers_for_destroyed_callee_guarantee_particle_contexts = (
            self._generate_triggers_for_destroyed_callee_guarantee_particles(
                names,
                action_execution_contexts_by_execution,
            )
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
                action_execution_contexts_by_execution,
            ),
            binding_hole_fanouts=self._generate_binding_hole_fanouts(
                names,
                action_execution_contexts_by_execution,
            ),
            action_executions=list(action_execution_contexts_by_execution.values()),
            triggers_for_destroyed_callee_guarantee_particles=(
                triggers_for_destroyed_callee_guarantee_particle_contexts
            ),
            callee_binding_joins=callee_binding_join_contexts,
            guarantees=guarantees.context,
            accepts_destruction_connections=(
                self._plan.accepts_destruction_connections
            ),
            trace_operations=self._operation_labels is not None,
        )
        return GeneratedExecution(
            context=context,
            binding_hole_method_names=names.binding_hole_method_names,
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
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
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
            guarantee_dependent_destroy_position = None
            operation = fragment.guarantee_dependent_destroy
            if operation is not None:
                guarantee_dependent_destroy_position = (
                    template_context.DestructionPositionContext(
                        member_name=names.destruction_positions[operation],
                        position=statement_generator.build_position(operation.target),
                    )
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
                    callee_binding_join_method_names_that_depend_on_fragment=[
                        names.callee_binding_join_method_names[callee_binding_join]
                        for callee_binding_join in (
                            fragment.callee_binding_joins_that_depend_on_fragment
                        )
                    ],
                    # TODO: Do not make a triggered Action Execution inherit the
                    # triggering Particle Operation as a runtime dependency. The
                    # particle operation dependency graph has no such dependency,
                    # but initialization currently follows the triggering Particle
                    # Operation's completion hook.
                    triggered_action_successors=[
                        action_execution_contexts_by_execution[action_execution]
                        for action_execution in fragment.action_execution_successors
                    ],
                    triggered_action_execution_callee_binding_join_method_names=[
                        names.callee_binding_join_method_names[callee_binding_join]
                        for callee_binding_join in (
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
                    guarantee_dependent_destroy_position=(
                        guarantee_dependent_destroy_position
                    ),
                )
            )
        return fragments

    def _generate_binding_hole_fanouts(
        self,
        names: action_names.ActionNames,
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
    ) -> list[template_context.BindingHoleFanoutContext]:
        return [
            template_context.BindingHoleFanoutContext(
                binding_hole_method_name=names.binding_hole_method_names[
                    binding_hole_fanout.binding_hole
                ],
                fragment_method_names=[
                    names.fragments[fragment]
                    for fragment in binding_hole_fanout.fragments
                ],
                callee_binding_join_method_names=[
                    names.callee_binding_join_method_names[callee_binding_join]
                    for callee_binding_join in binding_hole_fanout.callee_binding_joins
                ],
                destructor_executions=[
                    action_execution_contexts_by_execution[destructor_execution]
                    for destructor_execution in (
                        binding_hole_fanout.destructor_executions
                    )
                ],
            )
            for binding_hole_fanout in self._plan.binding_hole_fanouts
        ]

    def _generate_callee_binding_joins(
        self,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
    ) -> list[template_context.CalleeBindingJoinContext]:
        callee_binding_join_contexts: list[
            template_context.CalleeBindingJoinContext
        ] = []
        for callee_binding_join in self._plan.callee_binding_joins:
            execution = callee_binding_join.execution
            callee_binding_join_contexts.append(
                template_context.CalleeBindingJoinContext(
                    triggered_action_execution_name=(
                        names.triggered_actions[execution].execution_name
                    ),
                    callee_binding_hole_method_name=self._generated_actions[
                        execution.callee_action_name
                    ].binding_hole_method_names[
                        callee_binding_join.callee_binding_hole
                    ],
                    method_name=names.callee_binding_join_method_names[
                        callee_binding_join
                    ],
                    dependency_count=callee_binding_join.dependency_count,
                    destruction_positions=[
                        template_context.DestructionPositionContext(
                            member_name=names.destruction_positions[operation],
                            position=statement_generator.build_position(
                                operation.target
                            ),
                        )
                        for operation in (
                            callee_binding_join.contributed_destruction_operations
                        )
                    ],
                )
            )
        return callee_binding_join_contexts

    def _generate_triggers_for_destroyed_callee_guarantee_particles(
        self,
        names: action_names.ActionNames,
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
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
            callee_binding_join_method_names: list[str] = []
            for (
                callee_binding_join
            ) in trigger_for_destroyed_callee_guarantee_particle.callee_binding_joins:
                callee_binding_join_method_names.append(
                    names.callee_binding_join_method_names[callee_binding_join]
                )
            contexts.append(
                template_context.TriggerForDestroyedCalleeGuaranteeParticleContext(
                    method_name=triggered_action_names.canonical_name,
                    action_execution=(
                        action_execution_contexts_by_execution[
                            trigger_for_destroyed_callee_guarantee_particle.execution
                        ]
                    ),
                    callee_binding_join_method_names=callee_binding_join_method_names,
                )
            )
        return contexts
