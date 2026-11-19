# Rejected: ruff:ARG001, pyright:reportUnnecessaryContains, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a membership test that always fails."""

from __future__ import annotations


def is_recorded(recorded: set[tuple[str, int]], name: str, count: int) -> bool:
    """Return whether `name` and `count` are recorded."""
    key = None
    return key in recorded
