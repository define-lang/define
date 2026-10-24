"""Literal Python generation for Encoding Operation definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import msgspec

from define.compiler import constants
from define.compiler.codegen.literal.python import (
    naming,
    renderer,
    value_types,
)
from define.compiler.validator import codegen_input

if TYPE_CHECKING:
    from define.compiler import ast


class _BinaryOperation(msgspec.Struct, frozen=True):
    """A computer operation that combines two views with an infix operator."""

    operator: renderer.BinaryOperator
    left_view: str
    right_view: str
    result_view: str


class _LiteralOperation(msgspec.Struct, frozen=True):
    """A computer operation that combines a view with a literal and writes the result back to the view."""

    operator: renderer.BinaryOperator
    view: str
    # Already in the view's encoding.
    literal: str


class _PrefixOperation(msgspec.Struct, frozen=True):
    """A computer operation that applies a prefix operator to a view and writes the result back to the view."""

    operator: renderer.PrefixOperator
    view: str


class _ExpressionOperation(msgspec.Struct, frozen=True):
    """A computer operation written as a fixed expression over views."""

    operator: renderer.ExpressionOperator
    operand_views: tuple[str, ...]
    result_view: str


class _FunctionCall(msgspec.Struct, frozen=True):
    """A computer operation that calls a Python library function."""

    function: renderer.FunctionReference
    argument_views: tuple[str, ...]
    result_view: str


type _ComputerOperation = (
    _BinaryOperation
    | _LiteralOperation
    | _PrefixOperation
    | _ExpressionOperation
    | _FunctionCall
)


def _binary_function_call(module_name: str, function_name: str) -> _FunctionCall:
    return _FunctionCall(
        function=renderer.FunctionReference(
            function_name=function_name, module_name=module_name
        ),
        argument_views=("view<a>", "view<b>"),
        result_view="view<result>",
    )


# The computer operations that the compiler knows how to perform, by the
# Encoding Operation that executes them.
_COMPUTER_OPERATIONS: Final[dict[str, _ComputerOperation]] = {
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/and>": _BinaryOperation(
        operator=renderer.BinaryOperator.BitwiseAnd(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/or>": _BinaryOperation(
        operator=renderer.BinaryOperator.BitwiseOr(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/exclusive_or>": _BinaryOperation(
        operator=renderer.BinaryOperator.ExclusiveOr(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/and>": _BinaryOperation(
        operator=renderer.BinaryOperator.And(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/not>": _PrefixOperation(
        operator=renderer.PrefixOperator.Not(), view="view<value>"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/or>": _BinaryOperation(
        operator=renderer.BinaryOperator.Or(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/exclusive_or>": _BinaryOperation(
        operator=renderer.BinaryOperator.ExclusiveOr(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/absolute_value>": _FunctionCall(
        function=renderer.FunctionReference(
            function_name="abs", module_name="builtins"
        ),
        argument_views=("view<value>",),
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/add>": _BinaryOperation(
        operator=renderer.BinaryOperator.Add(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/decrement>": _LiteralOperation(
        operator=renderer.BinaryOperator.Subtract(),
        view="view<value>",
        literal="1",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/increment>": _LiteralOperation(
        operator=renderer.BinaryOperator.Add(),
        view="view<value>",
        literal="1",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/less_than_or_equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThanOrEqual(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/maximum>": _binary_function_call(
        "builtins", "max"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/minimum>": _binary_function_call(
        "builtins", "min"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/multiply>": _BinaryOperation(
        operator=renderer.BinaryOperator.Multiply(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/negate>": _PrefixOperation(
        operator=renderer.PrefixOperator.Negate(), view="view<value>"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/subtract>": _BinaryOperation(
        operator=renderer.BinaryOperator.Subtract(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/add>": _BinaryOperation(
        operator=renderer.BinaryOperator.Add(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/decrement_saturating>": _ExpressionOperation(
        operator=renderer.ExpressionOperator.SaturatingDecrement(),
        operand_views=("view<value>",),
        result_view="view<value>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/increment>": _LiteralOperation(
        operator=renderer.BinaryOperator.Add(),
        view="view<value>",
        literal="1",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/less_than_or_equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThanOrEqual(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/maximum>": _binary_function_call(
        "builtins", "max"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/minimum>": _binary_function_call(
        "builtins", "min"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/multiply>": _BinaryOperation(
        operator=renderer.BinaryOperator.Multiply(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/subtract>": _BinaryOperation(
        operator=renderer.BinaryOperator.Subtract(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/subtract_saturating>": _ExpressionOperation(
        operator=renderer.ExpressionOperator.SaturatingSubtract(),
        operand_views=("view<a>", "view<b>"),
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/greater_than_or_equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.GreaterThanOrEqual(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/less_than_or_equal>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThanOrEqual(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
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

    def generate(self) -> renderer.EncodingOperationDefinition:
        """Build the template context for this Encoding Operation's function."""
        definition = self._operation_input.definition
        function = self._converter.function_reference(definition.typed_name)
        callees: list[renderer.FunctionReference] = []
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
        statements: list[renderer.EncodingOperationStatement] = []
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
        parameters: list[renderer.TypedLocalName] = []
        results: list[renderer.TypedLocalName] = []
        for view in definition.views:
            view_local = renderer.TypedLocalName(
                name=view_names[view.typed_name.source_typed_name],
                python_type=value_types.encoded_python_value_type(
                    view.quality_assignment_block
                ),
            )
            if view.is_input:
                parameters.append(view_local)
            if view.is_output:
                results.append(view_local)
        result_names = [result.name for result in results]
        return renderer.EncodingOperationDefinition(
            function_name=function.function_name,
            module_name=function.module_name,
            parameters=parameters,
            statements=statements,
            results=results,
            # Returning the last statement's expression avoids assigning
            # locals only to return them.
            return_last_statement=bool(results) and last_written_names == result_names,
            imports=imports,
        )

    def _call(
        self,
        execution: codegen_input.EncodingOperationExecution,
        view_names: dict[str, str],
    ) -> renderer.EncodingOperationStatement.Call:
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
        return renderer.EncodingOperationStatement.Call(
            function=self._converter.function_reference(execution.encoding_operation),
            arguments=arguments,
            results=results,
        )

    @staticmethod
    def _computer_operation(
        definition: ast.EncodingOperationDefinition, view_names: dict[str, str]
    ) -> tuple[renderer.EncodingOperationStatement, list[str]]:
        """Return the statement that performs the Encoding Operation's computer operation, and the local names it assigns."""
        computer_operation = _lookup_computer_operation(definition)
        match computer_operation:
            case _BinaryOperation():
                result = view_names[computer_operation.result_view]
                return renderer.EncodingOperationStatement.BinaryOperation(
                    operator=computer_operation.operator,
                    left=view_names[computer_operation.left_view],
                    right=view_names[computer_operation.right_view],
                    result=result,
                ), [result]
            case _LiteralOperation():
                value = view_names[computer_operation.view]
                return renderer.EncodingOperationStatement.BinaryOperation(
                    operator=computer_operation.operator,
                    left=value,
                    right=computer_operation.literal,
                    result=value,
                ), [value]
            case _PrefixOperation():
                value = view_names[computer_operation.view]
                return renderer.EncodingOperationStatement.PrefixOperation(
                    operator=computer_operation.operator, operand=value, result=value
                ), [value]
            case _ExpressionOperation():
                result = view_names[computer_operation.result_view]
                return renderer.EncodingOperationStatement.ExpressionOperation(
                    operator=computer_operation.operator,
                    operands=[
                        view_names[view] for view in computer_operation.operand_views
                    ],
                    result=result,
                ), [result]
            case _FunctionCall():
                result = view_names[computer_operation.result_view]
                return renderer.EncodingOperationStatement.Call(
                    function=computer_operation.function,
                    arguments=[
                        view_names[view] for view in computer_operation.argument_views
                    ],
                    results=[result],
                ), [result]


def _lookup_computer_operation(
    definition: ast.EncodingOperationDefinition,
) -> _ComputerOperation:
    # Code generation relies on validation to report computer operations that
    # the compiler cannot perform.
    return _COMPUTER_OPERATIONS[definition.typed_name.full_typed_name]
