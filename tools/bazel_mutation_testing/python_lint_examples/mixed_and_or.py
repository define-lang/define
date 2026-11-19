# Rejected: ruff:RUF021
# Rejected in mutation runs: nothing
"""An `or` that became `and`, which mixes `and` and `or` without parentheses."""

from __future__ import annotations


def is_incomplete(name: str | None, value: str | None, count: int) -> bool:
    """Return whether the name or value is missing, or there is no count."""
    return name is None or value is None and count == 0
