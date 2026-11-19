# Rejected: ruff:F841, pyright:reportUnusedVariable
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves a variable unused."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def labels(names: Iterable[str]) -> list[str | None]:
    """Return a label for each of `names`."""
    found: list[str | None] = []
    for name in names:
        label = name.upper()
        found.append(None)
    return found
