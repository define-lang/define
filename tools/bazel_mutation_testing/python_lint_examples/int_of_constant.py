# Rejected: ruff:ARG001, ruff:RUF046, ruff:UP018, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""A call whose first argument was deleted, which converts a constant to an int."""

from __future__ import annotations


def binary_as_decimal(bits: str) -> str:
    """Return the decimal digits of the binary number `bits`."""
    return str(int(2))
