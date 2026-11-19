# Rejected: pyright:reportOptionalSubscript, pyright:reportUnknownVariableType
# Rejected in mutation runs: pyright:reportOptionalSubscript, pyright:reportUnknownVariableType
"""A call that lost its default, which indexes what may be None."""

from __future__ import annotations


def first_count(counts: dict[str, list[int]], name: str) -> int:
    """Return the first count of `name`."""
    return counts.get(name)[0]
