# Rejected: ruff:B005
# Rejected in mutation runs: nothing
"""A string whose characters were repeated, which strips the same characters from digits as before."""

from __future__ import annotations


def is_whole(number: str) -> bool:
    """Whether the digits after the decimal point of `number` are all zeros."""
    _, _, fraction = number.partition(".")
    return not fraction.strip("XX0XX")
