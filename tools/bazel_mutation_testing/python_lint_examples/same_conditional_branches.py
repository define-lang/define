# Rejected: ruff:RUF034
# Rejected in mutation runs: nothing
"""A conditional expression whose else value was changed to match its if value."""

from __future__ import annotations


def digits_start(number: str) -> int:
    """Return where the digits of `number` start, after any minus sign."""
    return 1 if number.startswith("-") else 1
