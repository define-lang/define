# Rejected: ruff:F821, pyright:reportUndefinedVariable, pyright:reportUnknownVariableType
# Rejected in mutation runs: ruff:F821, pyright:reportUndefinedVariable, pyright:reportUnknownVariableType
"""A cast whose quoted type became a name that is not defined."""

from __future__ import annotations

import typing


def first_name(names: dict[str, object]) -> str:
    """Return the name that `names` holds under "first"."""
    return typing.cast("XXstrXX", names["first"])
