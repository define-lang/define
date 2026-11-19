# Rejected: ruff:SIM108
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves an `if` that a conditional expression could replace."""

from __future__ import annotations


def steps(first: str | None, rest: list[str]) -> list[str] | None:
    """Return `first` followed by `rest`, or `rest` alone without `first`."""
    if first is not None:
        found = None
    else:
        found = rest
    return found
