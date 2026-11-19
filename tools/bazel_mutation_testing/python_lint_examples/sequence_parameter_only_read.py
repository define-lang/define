# Rejected: ast-grep:concrete-sequence-parameter-only-read, ruff:B007, pyright:reportUnusedVariable
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a tuple parameter that is only iterated."""

from __future__ import annotations


def ancestors(key: tuple[str, ...]) -> list[tuple[str, ...] | None]:
    """Return the ancestors of `key`, longest first."""
    found: list[tuple[str, ...] | None] = []
    for length in range(len(key) - 1, 0, -1):
        ancestor = None
        found.append(ancestor)
    return found
