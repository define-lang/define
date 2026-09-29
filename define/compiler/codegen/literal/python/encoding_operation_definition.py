"""Literal Python generation for Encoding Operation definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import msgspec

from define.compiler import constants
from define.compiler.codegen.literal.python import naming, template_context
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from define.compiler import ast


class _InfixAdd(msgspec.Struct, frozen=True):
    """A computer operation that adds two views with infix addition."""

    left_view: str
    right_view: str
    result_view: str


# The computer operations that the compiler knows how to perform, by the
# Encoding Operation that executes them.
_COMPUTER_OPERATIONS: Final = {
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_add>": _InfixAdd(
        left_view="view<a>", right_view="view<b>", result_view="view<sum>"
    )
}


@final
class EncodingOperationDefinitionGenerator:
    """Generate the function that performs an Encoding Operation."""

    def __init__(
        self,
        operation_input: codegen_input.EncodingOperationCodegenInput,
        converter: naming.NameConverter,
    ):
        """Initialize from the validated Encoding Operation and the shared name converter."""
        self._operation_input = operation_input
        self._converter = converter

    def generate(self) -> template_context.EncodingOperationDefinitionContext:
        """Build the template context for this Encoding Operation's function."""
        definition = self._operation_input.definition
        function = self._converter.function_reference(definition.typed_name)
        callees: list[naming.FunctionReference] = []
        for step in self._operation_input.steps:
            if isinstance(step, codegen_input.EncodingOperationExecution):
                callees.append(
                    self._converter.function_reference(step.encoding_operation)
                )
        imports = {
            callee.module_name
            for callee in callees
            if callee.module_name != function.module_name
        }
        names = naming.LocalNameAllocator()
        # A view's local name must not hide an imported module, or a function in
        # this module that the Encoding Operation calls.
        names.reserve_module_first_names(imports)
        names.reserve_module_first_names(
            callee.function_name
            for callee in callees
            if callee.module_name == function.module_name
        )
        view_names: dict[str, str] = {}
        for view in definition.views:
            view_names[view.typed_name.source_typed_name] = names.allocate(
                view.typed_name.name_content.name
            )
        statements: list[template_context.EncodingOperationStatementContext] = []
        # The local names that the last statement assigns, in order.
        last_written_names: list[str] = []
        for step in self._operation_input.steps:
            if isinstance(step, codegen_input.EncodingOperationExecution):
                call = self._call(step, view_names)
                statements.append(call)
                last_written_names = call.results
            else:
                computer_operation = self._computer_operation(definition, view_names)
                statements.append(computer_operation)
                last_written_names = [computer_operation.result]
        results = [
            view_names[view.typed_name.source_typed_name]
            for view in definition.views
            if view.is_output
        ]
        return template_context.EncodingOperationDefinitionContext(
            function_name=function.function_name,
            module_name=function.module_name,
            parameters=[
                view_names[view.typed_name.source_typed_name]
                for view in definition.views
                if view.is_input
            ],
            statements=statements,
            results=results,
            # Returning the last statement's expression avoids assigning
            # locals only to return them.
            return_last_statement=bool(results) and last_written_names == results,
            imports=sorted(imports),
        )

    def _call(
        self,
        execution: codegen_input.EncodingOperationExecution,
        view_names: dict[str, str],
    ) -> template_context.CallContext:
        arguments: list[str] = []
        results: list[str] = []
        for argument in execution.arguments:
            looking_at = argument.looking_at
            if isinstance(looking_at, str):
                looked_at = looking_at
            else:
                looked_at = view_names[looking_at.source_typed_name]
            if argument.interface_view.is_input:
                arguments.append(looked_at)
            if argument.interface_view.is_output:
                results.append(looked_at)
        return template_context.CallContext(
            function=self._converter.function_reference(execution.encoding_operation),
            arguments=arguments,
            results=results,
        )

    @staticmethod
    def _computer_operation(
        definition: ast.EncodingOperationDefinition, view_names: dict[str, str]
    ) -> template_context.InfixAddContext:
        # Code generation relies on validation to report computer operations
        # that the compiler cannot perform.
        computer_operation = _COMPUTER_OPERATIONS[definition.typed_name.full_typed_name]
        return template_context.InfixAddContext(
            left=view_names[computer_operation.left_view],
            right=view_names[computer_operation.right_view],
            result=view_names[computer_operation.result_view],
        )
