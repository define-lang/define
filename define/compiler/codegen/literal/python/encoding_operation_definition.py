"""Literal Python generation for Encoding Operation definitions."""

from __future__ import annotations

import typing
from typing import Final, final

import msgspec

from define.compiler import ast, computer_operations, constants
from define.compiler.codegen.literal.python import (
    operation_function,
    renderer,
    value_types,
)

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.association_resolution import concrete_program
    from define.compiler.codegen.literal.python import naming


class _BinaryOperation(msgspec.Struct, frozen=True):
    """A computer operation that combines two views with an infix operator."""

    operator: renderer.BinaryOperator
    left_view: str
    right_view: str
    result_view: str


class _PrefixOperation(msgspec.Struct, frozen=True):
    """A computer operation that applies a prefix operator to a view."""

    operator: renderer.PrefixOperator
    operand_view: str
    result_view: str


class _FunctionCall(msgspec.Struct, frozen=True):
    """A computer operation that calls a Python library function."""

    function: renderer.FunctionReference
    argument_views: tuple[str, ...]
    result_view: str


type _ComputerOperation = _BinaryOperation | _PrefixOperation | _FunctionCall


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
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/equals>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
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
        operator=renderer.PrefixOperator.Not(),
        operand_view="view<a>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/absolute_value>": _FunctionCall(
        function=renderer.FunctionReference(
            function_name="abs", module_name="builtins"
        ),
        argument_views=("view<a>",),
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/add>": _BinaryOperation(
        operator=renderer.BinaryOperator.Add(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
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
        operator=renderer.PrefixOperator.Negate(),
        operand_view="view<a>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/add>": _BinaryOperation(
        operator=renderer.BinaryOperator.Add(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/add_integer>": _BinaryOperation(
        operator=renderer.BinaryOperator.Add(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
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
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/negate>": _PrefixOperation(
        operator=renderer.PrefixOperator.Negate(),
        operand_view="view<a>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/less_than>": _BinaryOperation(
        operator=renderer.BinaryOperator.LessThan(),
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
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/equals>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/maximum>": _binary_function_call(
        "builtins", "max"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/equals>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/maximum>": _binary_function_call(
        "builtins", "max"
    ),
    f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/equals>": _BinaryOperation(
        operator=renderer.BinaryOperator.Equal(),
        left_view="view<a>",
        right_view="view<b>",
        result_view="view<result>",
    ),
}
# Validation accepts exactly the computer operations that the compiler knows
# how to perform, so code generation must perform every one of them.
if _COMPUTER_OPERATIONS.keys() != computer_operations.PERFORMABLE:
    raise RuntimeError(
        "Python code generation does not perform exactly the computer operations"
        + " that the compiler knows how to perform: "
        + f"{sorted(_COMPUTER_OPERATIONS.keys() ^ computer_operations.PERFORMABLE)}"
    )


@final
class _ComputerOperationStatement:
    """Performs an Encoding Operation's computer operation from the compiler's table of computer operations."""

    def __init__(self, definition: ast.EncodingOperationDefinition):
        """Initialize from the Encoding Operation whose computer operation this performs."""
        self._computer_operation = _lookup_computer_operation(definition)

    @property
    def callee(self) -> renderer.FunctionReference | None:
        """The library function that the computer operation calls, if it calls one."""
        if isinstance(self._computer_operation, _FunctionCall):
            return self._computer_operation.function
        return None

    def statement(
        self, view_names: Mapping[str, str]
    ) -> tuple[renderer.OperationStatement, list[str]]:
        """Return the statement that performs the computer operation, and the local names it assigns."""
        computer_operation = self._computer_operation
        match computer_operation:
            case _BinaryOperation():
                result = view_names[computer_operation.result_view]
                return renderer.OperationStatement.BinaryOperation(
                    operator=computer_operation.operator,
                    left=view_names[computer_operation.left_view],
                    right=view_names[computer_operation.right_view],
                    result=result,
                ), [result]
            case _PrefixOperation():
                result = view_names[computer_operation.result_view]
                return renderer.OperationStatement.PrefixOperation(
                    operator=computer_operation.operator,
                    operand=view_names[computer_operation.operand_view],
                    result=result,
                ), [result]
            case _FunctionCall():
                result = view_names[computer_operation.result_view]
                return renderer.OperationStatement.Call(
                    function=computer_operation.function,
                    arguments=[
                        view_names[view] for view in computer_operation.argument_views
                    ],
                    results=[result],
                ), [result]


def generate_encoding_operation(
    operation_input: concrete_program.ConcreteEncodingOperation,
    converter: naming.NameConverter,
) -> renderer.OperationFunction:
    """Build the template context for the function that performs an Encoding Operation."""
    definition = operation_input.definition
    function = converter.function_reference(definition.typed_name)
    view_python_types: dict[str, str] = {}
    for view in definition.views:
        view_python_types[view.typed_name.source_typed_name] = (
            value_types.encoded_python_value_type(view.quality_assignment_block)
        )
    if not isinstance(operation_input.body, ast.ComputerOperationExecutionStatement):
        return operation_function.generate_step_function(
            converter,
            function,
            definition.views,
            view_python_types,
            operation_input.body,
        )
    computer_operation = _ComputerOperationStatement(definition)
    callees: list[renderer.FunctionReference] = []
    if computer_operation.callee is not None:
        callees.append(computer_operation.callee)
    function_locals = operation_function.name_function_locals(
        function, definition.views, callees
    )
    statement, last_written_names = computer_operation.statement(
        function_locals.view_names
    )
    return operation_function.finish_function(
        function,
        definition.views,
        view_python_types,
        function_locals,
        [statement],
        last_written_names,
    )


def _lookup_computer_operation(
    definition: ast.EncodingOperationDefinition,
) -> _ComputerOperation:
    # Code generation relies on validation to report computer operations that
    # the compiler cannot perform.
    return _COMPUTER_OPERATIONS[definition.typed_name.full_typed_name]
