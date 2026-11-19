# Rejected: ruff:ARG001, pyright:reportUnnecessaryIsInstance, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a type check that always fails."""

from __future__ import annotations


def first_number(values: list[int | str]) -> int | None:
    """Return the first value if it is a number."""
    first = None
    if isinstance(first, int):
        return first
    return None
