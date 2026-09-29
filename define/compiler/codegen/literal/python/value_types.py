"""Python types of Define values in generated code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from define.compiler import constants

if TYPE_CHECKING:
    from define.compiler import ast

# The type argument of positions whose particles have no value that code
# looking through them can use.
NO_VALUE: Final = "Never"
# TODO: Emit values of rationals as exact fractions, such as
# fractions.Fraction, instead of Python floats, which cannot represent most
# rationals. Encoding Operation functions are also typed as float.
_ENCODING_PYTHON_TYPES: Final = {constants.DECIMAL_ASCII_ENCODING: "float"}


def python_value_type(value_type: ast.GlobalTypedNameReference) -> str:
    """Return the Python type that generated code uses for values of a value type."""
    return _ENCODING_PYTHON_TYPES[
        constants.BUILT_IN_VALUE_ENCODINGS[value_type.full_typed_name]
    ]


def constrained_python_value_type(
    constraints: ast.PositionConstraintBlock | None,
) -> str:
    """Return the Python value type of particles that meet these constraints, or NO_VALUE when they have no value constraint."""
    if constraints is None or constraints.value_constraint is None:
        return NO_VALUE
    return python_value_type(constraints.value_constraint)
