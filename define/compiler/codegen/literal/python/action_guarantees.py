"""Literal Python guarantee generation for action executions."""

import typing
from collections.abc import Sequence
from dataclasses import dataclass

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_names,
    naming,
    template_context,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.validator.reference_graph import (
    operation_graph,
    operation_graph_model,
)


@dataclass(frozen=True, slots=True)
class GeneratedGuarantees:
    """Generated guarantee context, interface, and consumer registrations."""

    context: template_context.GuaranteesContext | None
    interface: action_context.GuaranteeInterface | None
    guarantee_registrations: Sequence[template_context.GuaranteeRegistrationContext]


_EMPTY_GENERATED_GUARANTEES = GeneratedGuarantees(None, None, ())


@typing.final
class ActionGuaranteesGenerator:
    """Generate guarantees for one literal Python execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        plan: action_plan.ActionPlan,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedAction
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
        """Generate guarantee classes and consumer registrations."""
        child_guarantees = self._child_guarantees()
        if not (
            self._plan.guarantee_publications
            or child_guarantees
            or self._has_guarantee_dependencies()
        ):
            return _EMPTY_GENERATED_GUARANTEES

        class_reference = self._converter.guarantees_class_reference(
            self._definition.typed_name
        )
        interface = action_context.GuaranteeInterface(
            class_reference=class_reference,
            child_guarantees=child_guarantees,
            guarantee_names_by_operation=self._guarantee_names_by_operation(),
        )
        return GeneratedGuarantees(
            self._guarantees_context(class_reference, child_guarantees),
            interface,
            self._guarantee_registrations(interface),
        )

    def _has_guarantee_dependencies(self) -> bool:
        return (
            any(fragment.guarantee_dependencies for fragment in self._plan.fragments)
            or any(
                triggered_input.guarantee_dependencies
                for triggered_input in self._plan.triggered_action_inputs
            )
            or bool(self._plan.guarantee_destructor_triggers)
        )

    def _child_guarantees(
        self,
    ) -> dict[operation_graph_model.ActionTrigger, action_context.ChildGuarantees]:
        child_guarantees: dict[
            operation_graph_model.ActionTrigger, action_context.ChildGuarantees
        ] = {}
        for action_trigger in self._plan.action_triggers:
            callee_interface = self._generated_actions[
                action_trigger.callee_action_name
            ].guarantee_interface
            if callee_interface is not None:
                child_guarantees[action_trigger] = action_context.ChildGuarantees(
                    self._names.child_guarantees[action_trigger],
                    callee_interface,
                )
        return child_guarantees

    def _guarantee_names_by_operation(
        self,
    ) -> dict[operation_graph_model.PositionOperationNode, str]:
        names: dict[operation_graph_model.PositionOperationNode, str] = {}
        for publication in self._plan.guarantee_publications:
            names[publication.operation] = self._names.guarantee_publications[
                publication
            ]
        return names

    def _guarantees_context(
        self,
        class_reference: naming.ClassReference,
        child_guarantees: dict[
            operation_graph_model.ActionTrigger, action_context.ChildGuarantees
        ],
    ) -> template_context.GuaranteesContext:
        return template_context.GuaranteesContext(
            class_name=class_reference.class_name,
            child_guarantees=[
                template_context.ChildGuaranteesContext(
                    name=child.member_name,
                    class_reference=child.callee_interface.class_reference,
                )
                for child in child_guarantees.values()
            ],
            publications=[
                self._names.guarantee_publications[publication]
                for publication in self._plan.guarantee_publications
            ],
        )

    def _guarantee_registrations(
        self,
        interface: action_context.GuaranteeInterface,
    ) -> list[template_context.GuaranteeRegistrationContext]:
        registrations: list[template_context.GuaranteeRegistrationContext] = []
        for fragment in self._plan.fragments:
            for dependency in fragment.guarantee_dependencies:
                child_guarantees_names, guarantee_name = self._names_for_guarantee_path(
                    interface, dependency
                )
                registrations.append(
                    template_context.GuaranteeRegistrationContext(
                        child_guarantees_names=child_guarantees_names,
                        guarantee_name=guarantee_name,
                        method_name=self._names.fragments[fragment],
                    )
                )
        for triggered_input in self._plan.triggered_action_inputs:
            for dependency in triggered_input.guarantee_dependencies:
                child_guarantees_names, guarantee_name = self._names_for_guarantee_path(
                    interface, dependency
                )
                registrations.append(
                    template_context.GuaranteeRegistrationContext(
                        child_guarantees_names=child_guarantees_names,
                        guarantee_name=guarantee_name,
                        method_name=self._names.triggered_inputs[triggered_input],
                    )
                )
        for destructor_trigger in self._plan.guarantee_destructor_triggers:
            child_guarantees_names, guarantee_name = self._names_for_guarantee_path(
                interface, destructor_trigger.guarantee_dependency
            )
            registrations.append(
                template_context.GuaranteeRegistrationContext(
                    child_guarantees_names=child_guarantees_names,
                    guarantee_name=guarantee_name,
                    method_name=self._names.guarantee_destructor_triggers[
                        destructor_trigger
                    ],
                )
            )
        return registrations

    @staticmethod
    def _names_for_guarantee_path(
        interface: action_context.GuaranteeInterface,
        guarantee_path: operation_graph.GuaranteePath,
    ) -> tuple[list[str], str]:
        current_interface = interface
        child_guarantees_names: list[str] = []
        for trigger in guarantee_path.triggers:
            child_guarantees = current_interface.child_guarantees[trigger]
            child_guarantees_names.append(child_guarantees.member_name)
            current_interface = child_guarantees.callee_interface
        return (
            child_guarantees_names,
            current_interface.guarantee_names_by_operation[guarantee_path.operation],
        )
