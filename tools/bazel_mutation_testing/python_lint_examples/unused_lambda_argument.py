# Rejected: ruff:ARG005
# Rejected in mutation runs: nothing
"""A call in a lambda whose argument became None, which leaves the lambda's argument unused."""

from __future__ import annotations


def sorted_names(names: list[str]):
    """Sort `names` by their length."""
    names.sort(key=lambda name: _length(None))


def _length(name: str | None) -> int:
    return len(name or "")
