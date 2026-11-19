# Rejected: ruff:ARG001, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves the caller's parameter unused."""

from __future__ import annotations


def _total(values: list[int] | None) -> int:
    return sum(values or [])


def total(values: list[int]) -> int:
    """Return the sum of `values`."""
    return _total(None)
