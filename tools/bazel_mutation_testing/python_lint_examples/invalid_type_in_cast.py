# Rejected: ruff:F722, pyright:reportUndefinedVariable, pyright:reportUnknownVariableType, unidentified error
# Rejected in mutation runs: ruff:F722, pyright:reportUndefinedVariable, pyright:reportUnknownVariableType, unidentified error
"""A cast whose quoted type became text that is not a type."""

from __future__ import annotations

import typing


def counts(values: dict[str, object]) -> dict[str, int]:
    """Return `values`, which holds counts."""
    return typing.cast("XXdict[str, int]XX", values)
