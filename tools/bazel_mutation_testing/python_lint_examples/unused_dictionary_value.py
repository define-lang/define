# Rejected: ruff:B007, ruff:PERF102, pyright:reportUnusedVariable
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves each value of a dictionary unused."""

from __future__ import annotations


def cleared(counts: dict[str, int]) -> dict[str, int | None]:
    """Return `counts` with every count cleared."""
    found: dict[str, int | None] = {}
    for name, count in counts.items():
        found[name] = None
    return found
