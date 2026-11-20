# Rejected: ruff:FURB148, ruff:B007, pyright:reportUnusedVariable
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves the index from `enumerate` unused."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def labels(names: Iterable[str]) -> list[str]:
    """Return a label for each of `names`, numbered from 0."""
    found: list[str] = []
    for index, name in enumerate(names):
        found.append(_label(None, name))
    return found


def _label(index: int | None, name: str) -> str:
    return f"{index}: {name}"
