"""Literal Python execution lowering for action definitions."""

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
    triggered_action_execution,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator.reference_graph import (
        operation_graph_labeler,
        operation_graph_model,
    )


@typing.final
class ActionExecutionGenerator:
    """Lower one action plan to a literal Python execution context."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedActionInterface
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

    def generate(self) -> action_context.GeneratedExecution:
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
        generated_guarantees = action_guarantees.ActionGuaranteesGenerator(
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
                generated_guarantees.consumptions,
                statement_generator,
            ).generate()
        )
        context = self._generate_execution_context(
            names,
            statement_generator,
            generated_guarantees.context,
            generated_guarantees.consumptions,
            action_execution_contexts_by_execution,
        )
        action_interface = self._generate_action_interface(context, names)
        return action_context.GeneratedExecution(context, action_interface)

    def _generate_execution_context(
        self,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
        guarantees_context: template_context.GuaranteesContext | None,
        guarantee_consumptions: action_guarantees.GeneratedGuaranteeConsumptions | None,
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
    ) -> template_context.ActionExecutionContext:
        callee_binding_plan_contexts = self._generate_callee_binding_plans(
            names,
            statement_generator,
            guarantee_consumptions,
        )
        init_methods = self._generate_init_methods(
            names,
            action_execution_contexts_by_execution,
        )
        deferred_guarantee_registrations: list[
            template_context.DeferredGuaranteeRegistrationContext
        ] = []
        if guarantee_consumptions is not None:
            deferred_guarantee_registrations = (
                guarantee_consumptions.deferred_registrations
            )
        destruction_positions: list[template_context.DestructionPositionContext] = []
        for operation, member_name in names.destruction_positions.items():
            destruction_positions.append(
                template_context.DestructionPositionContext(
                    member_name=member_name,
                    position=statement_generator.build_position(operation.target),
                )
            )
        # TODO: Emit comments identifying the Define source lines represented by
        # generated Action Execution and Particle Operation code.
        return template_context.ActionExecutionContext(
            execution_class_name=self._converter.execution_class_name(
                self._definition.typed_name.name_content.path.relative_path
            ),
            local_position_statements=statement_generator.build_local_positions(),
            destruction_positions=destruction_positions,
            fragments=self._generate_fragments(
                names,
                statement_generator,
                action_execution_contexts_by_execution,
                guarantee_consumptions,
            ),
            binding_hole_fanouts=self._generate_binding_hole_fanouts(
                names,
                action_execution_contexts_by_execution,
            ),
            action_executions=list(action_execution_contexts_by_execution.values()),
            creation_inits=self._generate_inits_context(
                names,
                self._plan.creation_inits,
                action_execution_contexts_by_execution,
            ),
            init_methods=init_methods,
            deferred_guarantee_registrations=deferred_guarantee_registrations,
            callee_binding_plans=callee_binding_plan_contexts,
            guarantees=guarantees_context,
            accepts_destruction_connections=(
                self._plan.accepts_destruction_connections
            ),
            trace_operations=self._operation_labels is not None,
        )

    def _generate_action_interface(
        self,
        context: template_context.ActionExecutionContext,
        names: action_names.ActionNames,
    ) -> action_context.GeneratedActionInterface:
        execution_member_names = {
            execution: execution_names.execution_name
            for execution, execution_names in names.action_executions.items()
        }
        return action_context.GeneratedActionInterface(
            needs_action=context.needs_action,
            binding_holes=names.binding_holes,
            guarantee_names_by_operation={
                guarantees.operation: guarantee_name
                for guarantees, guarantee_name in names.guarantees.items()
            },
            execution_member_names=execution_member_names,
            join_member_names=names.join_member_names,
            fragment_method_names=names.fragments,
            destruction_continuations=self._generate_destruction_continuations(names),
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
        guarantee_consumptions: action_guarantees.GeneratedGuaranteeConsumptions | None,
    ) -> list[template_context.ActionFragmentContext]:
        fragments: list[template_context.ActionFragmentContext] = []
        for fragment in self._plan.fragments:
            guarantee_name = None
            action_guarantees = fragment.guarantees
            if action_guarantees is not None:
                guarantee_name = names.guarantees[action_guarantees]
            guarantee_dependent_destroy_position = None
            operation = fragment.guarantee_dependent_destroy
            if operation is not None:
                guarantee_dependent_destroy_position = (
                    template_context.DestructionPositionContext(
                        member_name=names.destruction_positions[operation],
                        position=statement_generator.build_position(operation.target),
                    )
                )
            inline_callee_binding_plans: list[
                template_context.CalleeBindingPlanContext
            ] = []
            for callee_binding_plan in fragment.inline_callee_binding_plans:
                inline_callee_binding_plans.append(
                    self._generate_callee_binding_plan_context(
                        callee_binding_plan,
                        names,
                        statement_generator,
                        guarantee_consumptions,
                    )
                )
            fragments.append(
                template_context.ActionFragmentContext(
                    method_name=names.fragments[fragment],
                    statements=[
                        statement_generator.build_operation(operation)
                        for operation in fragment.operations
                    ],
                    inits=self._generate_inits_context(
                        names,
                        fragment.inits,
                        action_execution_contexts_by_execution,
                    ),
                    fanout_continuation_method_names=(
                        names.fanout_continuation_method_names(
                            fragment.fanout_continuations,
                        )
                    ),
                    inline_callee_binding_plans=inline_callee_binding_plans,
                    guarantee_name=guarantee_name,
                    dependency_count=fragment.dependency_count,
                    join_is_assigned_by_caller=fragment.join_is_assigned_by_caller,
                    requires_join_check=fragment.requires_join_check,
                    join_member_name=names.join_member_names.get(fragment),
                    continue_destroy_method_name=names.continue_destroy_methods.get(
                        fragment
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
        contexts: list[template_context.BindingHoleFanoutContext] = []
        for binding_hole_fanout in self._plan.binding_hole_fanouts.values():
            binding_hole_names = names.binding_holes[binding_hole_fanout.binding_hole]
            inits = self._generate_inits_context(
                names,
                binding_hole_fanout.inits,
                action_execution_contexts_by_execution,
            )
            contexts.append(
                template_context.BindingHoleFanoutContext(
                    binding_hole_method_name=binding_hole_names.method_name,
                    requires_join_check=binding_hole_fanout.requires_join_check,
                    join_member_name=names.join_member_names.get(binding_hole_fanout),
                    inits=inits,
                    separate_init_method_name=(
                        binding_hole_names.separate_init_method_name
                    ),
                    continuation_method_name=(
                        binding_hole_names.continuation_method_name
                    ),
                    fanout_continuation_method_names=(
                        names.fanout_continuation_method_names(
                            binding_hole_fanout.continuations,
                        )
                    ),
                )
            )
        return contexts

    def _generate_inits_context(
        self,
        names: action_names.ActionNames,
        inits: action_plan.InitPlan,
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
    ) -> template_context.InitContext:
        return template_context.InitContext(
            action_executions=[
                action_execution_contexts_by_execution[action_execution]
                for action_execution in inits.action_executions
            ],
            callee_binding_method_names=names.callee_binding_plan_method_names(
                inits.callee_binding_plans,
            ),
        )

    def _generate_callee_binding_plans(
        self,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
        guarantee_consumptions: action_guarantees.GeneratedGuaranteeConsumptions | None,
    ) -> list[template_context.CalleeBindingPlanContext]:
        callee_binding_plan_contexts: list[
            template_context.CalleeBindingPlanContext
        ] = []
        for callee_binding_plan in self._plan.callee_binding_method_plans:
            callee_binding_plan_contexts.append(
                self._generate_callee_binding_plan_context(
                    callee_binding_plan,
                    names,
                    statement_generator,
                    guarantee_consumptions,
                )
            )
        return callee_binding_plan_contexts

    def _generate_callee_binding_plan_context(
        self,
        callee_binding_plan: action_plan.CalleeBindingPlan,
        names: action_names.ActionNames,
        statement_generator: action_statements.ActionStatementsGenerator,
        guarantee_consumptions: action_guarantees.GeneratedGuaranteeConsumptions | None,
    ) -> template_context.CalleeBindingPlanContext:
        execution = callee_binding_plan.execution
        generated_callee = self._generated_actions[execution.callee_action_name]
        binding_hole_names = generated_callee.binding_holes[
            callee_binding_plan.callee_binding_hole
        ]
        post_init_guarantee_consumptions: list[
            template_context.GuaranteeConsumptionContext
        ] = []
        if guarantee_consumptions is not None:
            for (
                consumption_plan
            ) in callee_binding_plan.post_init_guarantee_consumption_plans:
                post_init_guarantee_consumptions.append(
                    guarantee_consumptions.context_by_plan[consumption_plan]
                )
        destruction_positions: list[template_context.DestructionPositionContext] = []
        for operation in callee_binding_plan.contributed_destruction_operations:
            destruction_positions.append(
                template_context.DestructionPositionContext(
                    member_name=names.destruction_positions[operation],
                    position=statement_generator.build_position(operation.target),
                )
            )
        return template_context.CalleeBindingPlanContext(
            action_execution_name=names.action_executions[execution].execution_name,
            callee_binding_hole_method_name=binding_hole_names.method_name,
            callee_continuation_method_name=(
                binding_hole_names.continuation_method_name
            ),
            method_name=names.callee_binding_plans.get(callee_binding_plan),
            invocation_method_name=names.callee_binding_invocations.get(
                callee_binding_plan
            ),
            invokes_callee_binding_hole=(
                callee_binding_plan.invokes_callee_binding_hole
            ),
            dependency_count=callee_binding_plan.dependency_count,
            join_is_assigned_by_caller=callee_binding_plan.join_is_assigned_by_caller,
            requires_join_check=callee_binding_plan.requires_join_check,
            join_member_name=names.join_member_names.get(callee_binding_plan),
            destruction_positions=destruction_positions,
            init_method_name=names.callee_binding_init_method_name(callee_binding_plan),
            post_init_join_assignments=[
                self._nested_callee_join_assignment_context(assignment, names)
                for assignment in callee_binding_plan.post_init_join_assignments
            ],
            post_init_guarantee_consumptions=(post_init_guarantee_consumptions),
        )

    def _nested_callee_join_assignment_context(
        self,
        assignment: action_plan.CalleeJoinAssignment,
        names: action_names.ActionNames,
    ) -> template_context.CalleeJoinAssignmentContext:
        execution_member_names, generated_callee = names.generated_execution_path(
            assignment.execution_path,
        )
        return template_context.CalleeJoinAssignmentContext(
            member_name=generated_callee.join_member_names[assignment.target],
            dependency_count=assignment.dependency_count,
            execution_member_names=execution_member_names,
        )

    def _generate_init_methods(
        self,
        names: action_names.ActionNames,
        action_execution_contexts_by_execution: dict[
            operation_graph_model.ActionExecution,
            template_context.TriggeredActionExecutionContext,
        ],
    ) -> list[template_context.InitMethodContext]:
        init_methods: list[template_context.InitMethodContext] = []
        for (
            consumption_plan,
            method_name,
        ) in names.guarantee_consumption_init_method_names.items():
            init_methods.append(
                template_context.InitMethodContext(
                    method_name,
                    self._generate_inits_context(
                        names,
                        consumption_plan.inits,
                        action_execution_contexts_by_execution,
                    ),
                )
            )
        return init_methods
