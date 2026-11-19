# Rejected: pyright:reportUnreachable
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a branch that cannot run."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def counts_before(names: Iterable[str]) -> list[int]:
    """Return, for each name after a name that starts with "p", how many names came before that one."""
    found: list[int] = []
    previous_count: int | None = None
    for count, name in enumerate(names):
        if previous_count is not None:
            found.append(previous_count)
        if name.startswith("p"):
            previous_count = None
        _ = count
    return found
