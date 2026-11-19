# Rejected: ruff:B905
# Rejected in mutation runs: nothing
"""A call that lost its `strict=True` argument."""

from __future__ import annotations


def pairs(names: tuple[str, ...], values: tuple[int, ...]) -> list[tuple[str, int]]:
    """Return each of `names` with the value at the same place in `values`."""
    # ZIP: This relationship can only be created here because each value is
    # at its name's place.
    return list(zip(names, values))
