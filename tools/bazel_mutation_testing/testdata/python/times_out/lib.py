"""A function with mutants that never return."""

from __future__ import annotations


def first_multiple_from(step: int, limit: int) -> int:
    """Return the first multiple of `step` that is at least `limit`."""
    value = 0
    # Replacing `+=` with `-=` or `=` keeps `value` below `limit` forever.
    while value < limit:
        value += step
    return value
