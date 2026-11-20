# Rejected: ruff:SIM910
# Rejected in mutation runs: nothing
"""A default that became None, which `dict.get` returns without being told."""

from __future__ import annotations


def count(occurrences: dict[str, int], name: str) -> int | None:
    """Return how many times `name` occurs."""
    return occurrences.get(name, None)
