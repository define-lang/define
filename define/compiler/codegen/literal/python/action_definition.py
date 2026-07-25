"""Literal Python generation for action definitions."""

import typing

from define.compiler import ast
from define.compiler.codegen import action_plan
from define.compiler.codegen.literal.python import (
    action_context,
    action_execution,
    naming,
    template_context,
)
from define.compiler.data_structures import typed_name_dict


@typing.final
class ActionDefinitionGenerator:
    """Generate an action definition and its execution."""

    def __init__(
        self,
        definition: ast.ActionDefinition,
        converter: naming.NameConverter,
        role: action_context.ActionRole,
        generated_actions: typed_name_dict.TypedNameDict[
            ast.GlobalTypedName, action_context.GeneratedAction
        ],
        plan: action_plan.ActionPlan,
    ):
        """Initialize with one action and its already-generated callees."""
        self._definition = definition
        self._converter = converter
        self._role = role
        self._generated_actions = generated_actions
        self._plan = plan

    def generate(self) -> action_context.GeneratedAction:
        """Generate the action definition and its caller-facing interface."""
        name_content = self._definition.typed_name.name_content
        class_name = self._converter.class_name(name_content.path.relative_path)
        module_name = self._converter.module_name(name_content)
        interface_positions = [
            template_context.InterfacePositionContext(
                typed_name=local_definition.typed_name.source_typed_name,
                constraints=self._converter.constraints_to_class_references(
                    local_definition.constraints,
                ),
            )
            for local_definition in self._definition.interface_positions
        ]
        generated_execution = action_execution.ActionExecutionGenerator(
            self._definition,
            self._converter,
            self._generated_actions,
            self._plan,
        ).generate()
        context = action_context.ActionDefinitionContext(
            class_name=class_name,
            module_name=module_name,
            execution=generated_execution.context,
            role=self._role,
            interface_positions=interface_positions,
            implied_qualities=(
                self._converter.implied_qualities_to_class_references(
                    self._definition.quality_implications,
                )
            ),
        )
        return action_context.GeneratedAction(
            context,
            generated_execution.input_method_names,
            generated_execution.guarantee_interface,
        )
