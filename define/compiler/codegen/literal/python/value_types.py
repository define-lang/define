"""Python types of Define values in generated code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from define.compiler import constants, name_types

if TYPE_CHECKING:
    from collections.abc import Callable

    from define.compiler import ast
    from define.compiler.validator import codegen_input

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


def python_literal(literal: codegen_input.EncodedLiteral) -> str:
    """Return the Python expression for a literal's value."""
    return _ENCODING_PYTHON_LITERALS[literal.encoding](literal.content)


def python_value_type(value_type: ast.GlobalTypedNameReference) -> str:
    """Return the Python type that generated code uses for values of a value type."""
    return _ENCODING_PYTHON_TYPES[
        constants.BUILT_IN_VALUE_ENCODINGS[value_type.full_typed_name]
    ]


def encoded_python_value_type(block: ast.QualityAssignmentBlock) -> str:
    """Return the Python type that generated code uses for values with the encoding this block assigns."""
    # Generated code represents a value the same way in every encoding, so any
    # one encoding serves.
    for statement in block.statements:
        encoding = statement.typed_global_name
        if encoding.name_type == name_types.NameType.ENCODING:
            return _ENCODING_PYTHON_TYPES[encoding.full_typed_name]
    raise ValueError(
        "Validation requires every Encoding Operation view to have an encoding"
    )


def constrained_python_value_type(
    block: ast.QualityAssignmentBlock | None,
) -> str:
    """Return the Python value type of particles with these quality assignments, or NO_VALUE when they assign no value quality."""
    if block is None or block.value_quality is None:
        return NO_VALUE
    return python_value_type(block.value_quality)
