# Rejected: ruff:RUF059, pyright:reportUnusedVariable
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves an unpacked variable unused."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def suffixes(names: Iterable[str]) -> list[str | None]:
    """Return the part of each of `names` after its first dot."""
    found: list[str | None] = []
    for name in names:
        _, _, suffix = name.partition(".")
        found.append(None)
    return found
