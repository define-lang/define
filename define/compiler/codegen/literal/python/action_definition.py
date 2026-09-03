"""Literal Python generation for action definitions."""

from __future__ import annotations

import typing

from define.compiler.codegen.literal.python import (
    action_context,
    action_execution,
    naming,
    template_context,
)

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.codegen import action_plan
    from define.compiler.data_structures import typed_name_dict
    from define.compiler.validator.reference_graph import operation_graph_labeler


@typing.final
class ActionDefinitionGenerator:
    """Generate an action definition and its execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedActionInterface
        ],
        plan: action_plan.ActionPlan,
        view_point_create_plan: action_plan.ViewPointCreatePlan | None,
        operation_labels: operation_graph_labeler.OperationGraphLabeler | None,
        *,
        is_entry_point: bool,
    ):
        """Initialize with one action and its already-generated callees.

        ``operation_labels`` is present for traced generation and absent for
        ordinary generation.
        """
        self._definition = definition
        self._converter = converter
        self._is_entry_point = is_entry_point
        self._generated_actions = generated_actions
        self._plan = plan
        self._view_point_create_plan = view_point_create_plan
        self._operation_labels = operation_labels

    def generate(self) -> action_context.GeneratedActionDefinition:
        """Generate the action definition and its caller-facing interface."""
        name_content = self._definition.typed_name.name_content
        class_name = self._converter.class_name(name_content.path.relative_path)
        module_name = self._converter.module_name(name_content)
        interface_positions: list[template_context.InterfacePositionContext] = []
        for local_definition in self._definition.interface_positions:
            interface_positions.append(
                template_context.InterfacePositionContext(
                    typed_name=local_definition.typed_name.source_typed_name,
                    constraints=self._converter.constraints_to_class_references(
                        local_definition.constraints,
                    ),
                )
            )
        generated_execution = action_execution.ActionExecutionGenerator(
            self._definition,
            self._converter,
            self._generated_actions,
            self._plan,
            self._operation_labels,
        ).generate()
        (
            view_point_create_method_names,
            view_point_create_join_assignments,
        ) = self._view_point_create_context(generated_execution)
        context = action_context.ActionDefinitionContext(
            class_name=class_name,
            module_name=module_name,
            execution=generated_execution.context,
            is_entry_point=self._is_entry_point,
            interface_positions=interface_positions,
            view_point_create_method_names=view_point_create_method_names,
            view_point_create_join_assignments=view_point_create_join_assignments,
            implied_qualities=(
                self._converter.implied_qualities_to_class_references(
                    self._definition.quality_implications,
                )
            ),
            trace_operations=self._operation_labels is not None,
            trace_action_name=(
                self._operation_labels.entry_action_execution_name(
                    self._definition.typed_name
                )
                if self._operation_labels is not None
                else None
            ),
        )
        return action_context.GeneratedActionDefinition(
            context,
            generated_execution.action_interface,
        )

    def _view_point_create_context(
        self,
        generated_execution: action_context.GeneratedExecution,
    ) -> tuple[
        list[str],
        list[template_context.CalleeJoinAssignmentContext],
    ]:
        view_point_create_method_names: list[str] = []
        view_point_create_join_assignments: list[
            template_context.CalleeJoinAssignmentContext
        ] = []
        if self._view_point_create_plan is None:
            return (
                view_point_create_method_names,
                view_point_create_join_assignments,
            )
        for binding_hole in self._view_point_create_plan.binding_holes:
            view_point_create_method_names.append(
                generated_execution.action_interface.binding_holes[
                    binding_hole
                ].method_name
            )
        for assignment in self._view_point_create_plan.join_assignments:
            execution_member_names: list[str] = []
            action_interface = generated_execution.action_interface
            for execution in assignment.execution_path:
                execution_member_names.append(
                    action_interface.execution_member_names[execution]
                )
                action_interface = self._generated_actions[execution.callee_action_name]
            view_point_create_join_assignments.append(
                template_context.CalleeJoinAssignmentContext(
                    action_interface.join_member_names[assignment.target],
                    assignment.dependency_count,
                    execution_member_names,
                )
            )
        return (
            view_point_create_method_names,
            view_point_create_join_assignments,
        )
