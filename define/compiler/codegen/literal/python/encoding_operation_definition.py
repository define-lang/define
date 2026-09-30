"""Literal Python generation for Encoding Operation definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import msgspec

from define.compiler import constants
from define.compiler.codegen.literal.python import (
    naming,
    template_context,
    value_types,
)
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from define.compiler import ast


class _BinaryOperation(msgspec.Struct, frozen=True):
    """A computer operation that combines two views with an infix operator."""

    operator: template_context.BinaryOperator
    left_view: str
    right_view: str
    result_view: str


class _LiteralOperation(msgspec.Struct, frozen=True):
    """A computer operation that combines a view with a literal and writes the result back to the view."""

    operator: template_context.BinaryOperator
    view: str
    # Already in the view's encoding.
    literal: str


class _PrefixOperation(msgspec.Struct, frozen=True):
    """A computer operation that applies a prefix operator to a view and writes the result back to the view."""

    operator: template_context.PrefixOperator
    view: str


class _FunctionCall(msgspec.Struct, frozen=True):
    """A computer operation that calls a Python library function."""

    function: naming.FunctionReference
    argument_views: tuple[str, ...]
    result_view: str


def _unary_function_call(module_name: str, function_name: str) -> _FunctionCall:
    return _FunctionCall(
        function=naming.FunctionReference(
            function_name=function_name, module_name=module_name
        ),
        argument_views=("view<value>",),
        result_view="view<value>",
    )


def _binary_function_call(module_name: str, function_name: str) -> _FunctionCall:
    return _FunctionCall(
        function=naming.FunctionReference(
            function_name=function_name, module_name=module_name
        ),
        argument_views=("view<a>", "view<b>"),
        result_view="view<result>",
    )


# The computer operations that the compiler knows how to perform, by the
# Encoding Operation that executes them.
_COMPUTER_OPERATIONS: Final[
    dict[str, _BinaryOperation | _LiteralOperation | _PrefixOperation | _FunctionCall]
] = {
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/and>": _BinaryOperation(
        operator=template_context.BinaryOperator.AND,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/not>": _PrefixOperation(
        operator=template_context.PrefixOperator.NOT, view="view<value>"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/or>": _BinaryOperation(
        operator=template_context.BinaryOperator.OR,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/exclusive_or>": _BinaryOperation(
        operator=template_context.BinaryOperator.EXCLUSIVE_OR,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/absolute_value>": _unary_function_call(
        "builtins", "abs"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/ceiling>": _unary_function_call(
        "math", "ceil"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/equal>": _BinaryOperation(
        operator=template_context.BinaryOperator.EQUAL,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/floor>": _unary_function_call(
        "math", "floor"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_add>": _BinaryOperation(
        operator=template_context.BinaryOperator.ADD,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_decrement>": _LiteralOperation(
        operator=template_context.BinaryOperator.SUBTRACT,
        view="view<value>",
        literal="1",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_increment>": _LiteralOperation(
        operator=template_context.BinaryOperator.ADD,
        view="view<value>",
        literal="1",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_multiply>": _BinaryOperation(
        operator=template_context.BinaryOperator.MULTIPLY,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/less_than>": _BinaryOperation(
        operator=template_context.BinaryOperator.LESS_THAN,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/less_than_or_equal>": _BinaryOperation(
        operator=template_context.BinaryOperator.LESS_THAN_OR_EQUAL,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/maximum>": _binary_function_call(
        "builtins", "max"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/minimum>": _binary_function_call(
        "builtins", "min"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/infix_subtract>": _BinaryOperation(
        operator=template_context.BinaryOperator.SUBTRACT,
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/negate>": _PrefixOperation(
        operator=template_context.PrefixOperator.NEGATE, view="view<value>"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii/truncate>": _unary_function_call(
        "math", "trunc"
    ),
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
            else:
                computer_operation = _lookup_computer_operation(definition)
                if isinstance(computer_operation, _FunctionCall):
                    callees.append(computer_operation.function)
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
                computer_operation, last_written_names = self._computer_operation(
                    definition, view_names
                )
                statements.append(computer_operation)
        parameters: list[template_context.TypedLocalName] = []
        results: list[template_context.TypedLocalName] = []
        for view in definition.views:
            view_local = template_context.TypedLocalName(
                name=view_names[view.typed_name.source_typed_name],
                python_type=value_types.encoded_python_value_type(view.constraints),
            )
            if view.is_input:
                parameters.append(view_local)
            if view.is_output:
                results.append(view_local)
        result_names = [result.name for result in results]
        return template_context.EncodingOperationDefinitionContext(
            function_name=function.function_name,
            module_name=function.module_name,
            parameters=parameters,
            statements=statements,
            results=results,
            # Returning the last statement's expression avoids assigning
            # locals only to return them.
            return_last_statement=bool(results) and last_written_names == result_names,
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
            if isinstance(looking_at, codegen_input.EncodedLiteral):
                looked_at = value_types.python_literal(looking_at)
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
    ) -> tuple[template_context.EncodingOperationStatementContext, list[str]]:
        """Return the statement that performs the Encoding Operation's computer operation, and the local names it assigns."""
        computer_operation = _lookup_computer_operation(definition)
        match computer_operation:
            case _BinaryOperation():
                result = view_names[computer_operation.result_view]
                return template_context.BinaryOperationContext(
                    operator=computer_operation.operator,
                    left=view_names[computer_operation.left_view],
                    right=view_names[computer_operation.right_view],
                    result=result,
                ), [result]
            case _LiteralOperation():
                value = view_names[computer_operation.view]
                return template_context.BinaryOperationContext(
                    operator=computer_operation.operator,
                    left=value,
                    right=computer_operation.literal,
                    result=value,
                ), [value]
            case _PrefixOperation():
                value = view_names[computer_operation.view]
                return template_context.PrefixOperationContext(
                    operator=computer_operation.operator, operand=value, result=value
                ), [value]
            case _FunctionCall():
                result = view_names[computer_operation.result_view]
                return template_context.CallContext(
                    function=computer_operation.function,
                    arguments=[
                        view_names[view] for view in computer_operation.argument_views
                    ],
                    results=[result],
                ), [result]


def _lookup_computer_operation(
    definition: ast.EncodingOperationDefinition,
) -> _BinaryOperation | _LiteralOperation | _PrefixOperation | _FunctionCall:
    # Code generation relies on validation to report computer operations that
    # the compiler cannot perform.
    return _COMPUTER_OPERATIONS[definition.typed_name.full_typed_name]
