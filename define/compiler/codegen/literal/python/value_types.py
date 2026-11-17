"""Python types of Define values in generated code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from define.compiler import constants
from define.compiler.association_resolution import concrete_program

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from define.compiler import ast

# The type argument of positions whose particles have no value that code
# looking through them can use.
NO_VALUE: Final = "Never"
# TODO: Emit decimal values as exact fractions, such as fractions.Fraction,
# instead of Python floats, which cannot represent most decimals and so can
# also make decimal comparisons give the wrong answer.
_ENCODING_PYTHON_TYPES: Final = {
    constants.BINARY_ASCII_ENCODING: "int",
    constants.BOOLEAN_ASCII_ENCODING: "bool",
    constants.DECIMAL_ASCII_ENCODING: "float",
    constants.INTEGER_ASCII_ENCODING: "int",
    constants.NATURAL_ASCII_ENCODING: "int",
    constants.SCALAR_UTF8_ENCODING: "str",
}

_PYTHON_BOOLEANS: Final = {"true": "True", "false": "False"}


def _python_binary(content: str) -> str:
    return f"0b{content}"


def _python_boolean(content: str) -> str:
    return _PYTHON_BOOLEANS[content]


def _python_decimal(content: str) -> str:
    # Decimal, integer, and natural ASCII content is already a valid Python
    # number.
    return content


_PYTHON_STRING_ESCAPES: Final = {"\\": "\\\\", "\n": "\\n"}


def _python_scalar(content: str) -> str:
    # Python formatters such as ruff and Black write a double quote inside single
    # quotes rather than escaping it, so generated code stays unchanged when
    # formatted.
    if content == '"':
        return "'\"'"
    if content in _PYTHON_STRING_ESCAPES:
        escaped = _PYTHON_STRING_ESCAPES[content]
    elif content.isprintable():
        escaped = content
    else:
        # Code-point literals can set scalars that would be invisible or invalid
        # in Python source, such as NUL.
        escaped = f"\\U{ord(content):08x}"
    return f'"{escaped}"'


_ENCODING_PYTHON_LITERALS: Final[dict[str, Callable[[str], str]]] = {
    constants.BINARY_ASCII_ENCODING: _python_binary,
    constants.BOOLEAN_ASCII_ENCODING: _python_boolean,
    constants.DECIMAL_ASCII_ENCODING: _python_decimal,
    constants.INTEGER_ASCII_ENCODING: _python_decimal,
    constants.NATURAL_ASCII_ENCODING: _python_decimal,
    constants.SCALAR_UTF8_ENCODING: _python_scalar,
}


def python_literal(literal: concrete_program.EncodedLiteral) -> str:
    """Return the Python expression for a literal's value."""
    return _ENCODING_PYTHON_LITERALS[literal.encoding.full_typed_name](literal.content)


def encoding_python_value_type(encoding: ast.GlobalTypedNameReference) -> str:
    """Return the Python type that generated code uses for values in an encoding."""
    return _ENCODING_PYTHON_TYPES[encoding.full_typed_name]


def encoded_python_value_type(block: ast.QualityAssignmentBlock) -> str:
    """Return the Python type that generated code uses for values with the encoding this block assigns."""
    # Validation allows only encodings on an Encoding Operation view, and
    # generated code represents a value the same way in every encoding, so any
    # one encoding serves.
    return _ENCODING_PYTHON_TYPES[block.statements[0].typed_global_name.full_typed_name]


class PythonValueTypes:
    """The Python types of values in generated code, by their value qualities."""

    _value_encodings: Mapping[str, ast.GlobalTypedNameReference]
    _encoding_operations: Mapping[str, concrete_program.ConcreteEncodingOperation]

    def __init__(
        self,
        value_encodings: Mapping[str, ast.GlobalTypedNameReference],
        encoding_operations: Mapping[str, concrete_program.ConcreteEncodingOperation],
    ):
        """Initialize with each value quality's encoding and each Encoding Operation, both keyed by full typed name."""
        self._value_encodings = value_encodings
        self._encoding_operations = encoding_operations

    def python_value_type(self, value_quality: ast.GlobalTypedNameReference) -> str:
        """Return the Python type that generated code uses for values of a value quality."""
        return encoding_python_value_type(
            self._value_encodings[value_quality.full_typed_name]
        )

    def argument_python_value_type(
        self, runtime_operation: concrete_program.RuntimeOperation, view_name: str
    ) -> str:
        """Return the Python type of the values that the interface view named view_name of the runtime operation holds."""
        if isinstance(runtime_operation, concrete_program.CompositeValueOperation):
            return encoding_python_value_type(
                runtime_operation.view_encodings[view_name]
            )
        # Validation reports an argument for a view that the executed
        # operation does not define.
        view = cast(
            "ast.InterfaceViewDefinition",
            self._encoding_operations[
                runtime_operation.full_typed_name
            ].definition.get_view(view_name),
        )
        return encoded_python_value_type(view.quality_assignment_block)

    def assigned_python_value_type(
        self, block: ast.QualityAssignmentBlock | None
    ) -> str:
        """Return the Python value type of particles with these quality assignments, or NO_VALUE when they assign no value quality."""
        if block is None or block.value_quality is None:
            return NO_VALUE
        return self.python_value_type(block.value_quality)
