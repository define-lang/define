# Rejected: ruff:ARG001, pyright:reportUnnecessaryComparison, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a comparison that always holds."""

from __future__ import annotations


def is_first(seen: dict[str, str], name: str, value: str) -> bool:
    """Record `value` for `name`, and return whether it is the first."""
    first = None
    return first is not value
