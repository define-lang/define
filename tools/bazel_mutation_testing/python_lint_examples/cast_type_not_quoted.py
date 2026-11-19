# Rejected: ruff:TC006
# Rejected in mutation runs: nothing
"""A cast whose type became None, which Ruff wants quoted."""

from __future__ import annotations

import typing


def describe(values: dict[str, object]) -> str:
    """Return the value that `values` holds under "first", as text."""
    first = typing.cast(None, values["first"])
    return f"{first}"
