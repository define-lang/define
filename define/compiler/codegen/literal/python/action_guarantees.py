"""Literal Python guarantee generation for action executions."""

from __future__ import annotations

import typing
from dataclasses import dataclass

from define.compiler.codegen.literal.python import (
    action_context,
    action_names,
    naming,
    template_context,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.codegen import action_plan
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator.reference_graph import (
        operation_graph,
        operation_graph_model,
    )


@dataclass(frozen=True, slots=True)
class GeneratedGuaranteeConsumptions:
    """Generated Guarantee consumptions and their Action Execution associations."""

    context_by_plan: dict[
        action_plan.GuaranteeConsumptionPlan,
        template_context.GuaranteeConsumptionContext,
    ]
    consumptions_by_action_execution: dict[
        operation_graph_model.ActionExecution,
        list[template_context.GuaranteeConsumptionContext],
    ]
    deferred_registrations: list[template_context.DeferredGuaranteeRegistrationContext]


@dataclass(frozen=True, slots=True)
class GeneratedGuarantees:
    """Generated Guarantee template data and consumptions."""

    context: template_context.GuaranteesContext | None
    consumptions: GeneratedGuaranteeConsumptions | None


@dataclass(frozen=True, slots=True)
class _ActionExecutionGuaranteeConsumptions:
    """Generated Guarantee consumptions associated with Action Executions."""

    consumptions_by_action_execution: dict[
        operation_graph_model.ActionExecution,
        list[template_context.GuaranteeConsumptionContext],
    ]
    deferred_registrations: list[template_context.DeferredGuaranteeRegistrationContext]


@typing.final
class ActionGuaranteesGenerator:
    """Generate guarantees for one literal Python execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        plan: action_plan.ActionPlan,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedActionInterface
        ],
        names: action_names.ActionNames,
    ):
        """Initialize with one action plan and its generated callees."""
        self._definition = definition
        self._converter = converter
        self._plan = plan
        self._generated_actions = generated_actions
        self._names = names

    def generate(self) -> GeneratedGuarantees:
        """Generate Guarantee classes and consumptions."""
        context = None
        if self._names.guarantees:
            class_reference = self._converter.guarantees_class_reference(
                self._definition.typed_name
            )
            context = template_context.GuaranteesContext(
                class_name=class_reference.class_name,
                guarantee_names=self._names.guarantees.values(),
            )
        consumptions = None
        if self._plan.guarantee_consumption_plans:
            consumptions = self._generated_guarantee_consumptions()
        return GeneratedGuarantees(context, consumptions)

    def _generated_guarantee_consumptions(self) -> GeneratedGuaranteeConsumptions:
        consumptions: dict[
            action_plan.GuaranteeConsumptionPlan,
            template_context.GuaranteeConsumptionContext,
        ] = {}
        for consumption_plan in self._plan.guarantee_consumption_plans:
            consumptions[consumption_plan] = self._consumption_context(
                consumption_plan,
            )
        action_execution_consumptions = self._action_execution_consumptions(
            consumptions
        )
        return GeneratedGuaranteeConsumptions(
            consumptions,
            action_execution_consumptions.consumptions_by_action_execution,
            action_execution_consumptions.deferred_registrations,
        )

    def _consumption_context(
        self,
        consumption_plan: action_plan.GuaranteeConsumptionPlan,
    ) -> template_context.GuaranteeConsumptionContext:
        execution_member_names, guarantee_name = self._names_for_resolved_guarantee(
            consumption_plan.guarantee
        )
        return template_context.GuaranteeConsumptionContext(
            execution_member_names,
            guarantee_name,
            self._names.guarantee_consumption_init_method_names.get(consumption_plan),
            self._names.fanout_continuation_method_names(
                consumption_plan.continuations,
            ),
        )

    def _action_execution_consumptions(
        self,
        consumption_context_by_plan: dict[
            action_plan.GuaranteeConsumptionPlan,
            template_context.GuaranteeConsumptionContext,
        ],
    ) -> _ActionExecutionGuaranteeConsumptions:
        consumptions_by_action_execution: dict[
            operation_graph_model.ActionExecution,
            list[template_context.GuaranteeConsumptionContext],
        ] = {}
        deferred_registrations: list[
            template_context.DeferredGuaranteeRegistrationContext
        ] = []
        for planned_execution in self._plan.action_executions.values():
            consumptions, execution_deferred_registrations = (
                self._consumptions_for_action_execution(
                    planned_execution,
                    consumption_context_by_plan,
                )
            )
            deferred_registrations.extend(execution_deferred_registrations)
            if consumptions:
                consumptions_by_action_execution[planned_execution.execution] = (
                    consumptions
                )
        return _ActionExecutionGuaranteeConsumptions(
            consumptions_by_action_execution,
            deferred_registrations,
        )

    def _consumptions_for_action_execution(
        self,
        planned_execution: action_plan.ActionExecutionPlan,
        consumption_context_by_plan: dict[
            action_plan.GuaranteeConsumptionPlan,
            template_context.GuaranteeConsumptionContext,
        ],
    ) -> tuple[
        list[template_context.GuaranteeConsumptionContext],
        list[template_context.DeferredGuaranteeRegistrationContext],
    ]:
        consumptions: list[template_context.GuaranteeConsumptionContext] = []
        deferred_registrations: list[
            template_context.DeferredGuaranteeRegistrationContext
        ] = []
        for consumption_plan in planned_execution.guarantee_consumption_plans:
            consumptions.append(consumption_context_by_plan[consumption_plan])
        for deferred in planned_execution.deferred_guarantee_registrations:
            consumption, deferred_registration = self._deferred_registration(
                deferred,
                consumption_context_by_plan,
            )
            consumptions.append(consumption)
            deferred_registrations.append(deferred_registration)
        return consumptions, deferred_registrations

    def _deferred_registration(
        self,
        deferred: action_plan.DeferredGuaranteeRegistration,
        consumption_context_by_plan: dict[
            action_plan.GuaranteeConsumptionPlan,
            template_context.GuaranteeConsumptionContext,
        ],
    ) -> tuple[
        template_context.GuaranteeConsumptionContext,
        template_context.DeferredGuaranteeRegistrationContext,
    ]:
        execution_member_names, guarantee_name = self._names_for_resolved_guarantee(
            deferred.prerequisite_guarantee
        )
        method_name = self._names.deferred_guarantee_registration_method_names[deferred]
        consumption = template_context.GuaranteeConsumptionContext(
            execution_member_names,
            guarantee_name,
            method_name,
            [],
        )
        return (
            consumption,
            template_context.DeferredGuaranteeRegistrationContext(
                method_name,
                consumption_context_by_plan[deferred.consumption_plan],
            ),
        )

    def _names_for_resolved_guarantee(
        self,
        resolved_guarantee: operation_graph.ResolvedGuarantee,
    ) -> tuple[list[str], str]:
        """Return names for accessing the Guarantee from this execution.

        The list contains each Action Execution member leading to the callee
        that publishes the Guarantee. The string is the Guarantee member name
        exposed by that callee's generated interface.
        """
        execution_member_names, generated_callee = self._names.generated_execution_path(
            resolved_guarantee.executions,
        )
        return (
            execution_member_names,
            generated_callee.guarantee_names_by_operation[resolved_guarantee.operation],
        )
