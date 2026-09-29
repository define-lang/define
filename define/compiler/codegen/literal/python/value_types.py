"""Python types of Define values in generated code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from define.compiler import constants, name_types

if TYPE_CHECKING:
    from define.compiler import ast

# The type argument of positions whose particles have no value that code
# looking through them can use.
NO_VALUE: Final = "Never"
# TODO: Emit values of rationals as exact fractions, such as
# fractions.Fraction, instead of Python floats, which cannot represent most
# rationals.
_ENCODING_PYTHON_TYPES: Final = {
    constants.BOOLEAN_ASCII_ENCODING: "bool",
    constants.DECIMAL_ASCII_ENCODING: "float",
}


def python_value_type(value_type: ast.GlobalTypedNameReference) -> str:
    """Return the Python type that generated code uses for values of a value type."""
    return _ENCODING_PYTHON_TYPES[
        constants.BUILT_IN_VALUE_ENCODINGS[value_type.full_typed_name]
    ]


def encoded_python_value_type(constraints: ast.PositionConstraintBlock) -> str:
    """Return the Python type that generated code uses for values that meet these encoding constraints."""
    # Generated code represents a value the same way in every encoding, so any
    # one encoding serves.
    for requirement in constraints.requirements:
        encoding = requirement.typed_global_name
        if encoding.name_type == name_types.NameType.ENCODING:
            return _ENCODING_PYTHON_TYPES[encoding.full_typed_name]
    raise ValueError(
        "Validation requires every Encoding Operation view to have an encoding"
    )


def constrained_python_value_type(
    constraints: ast.PositionConstraintBlock | None,
) -> str:
    """Return the Python value type of particles that meet these constraints, or NO_VALUE when they have no value constraint."""
    if constraints is None or constraints.value_constraint is None:
        return NO_VALUE
    return python_value_type(constraints.value_constraint)
