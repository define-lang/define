"""A function with a mutant that only the type checker rejects."""

from __future__ import annotations


def total(values: list[int]) -> int:
    """Return the sum of `values`."""
    # Assigning None instead of 0 changes nothing that runs, but it is a type
    # error.
    start: int = 0
    return sum(values) + (start or 0)
