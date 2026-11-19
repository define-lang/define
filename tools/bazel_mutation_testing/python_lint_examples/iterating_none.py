# Rejected: pyright:reportOptionalIterable
# Rejected in mutation runs: pyright:reportOptionalIterable
"""A call that lost its default, which iterates over None."""

from __future__ import annotations


def total(counts: dict[str, list[int]], name: str) -> int:
    """Return the sum of the counts of `name`."""
    found = 0
    for count in counts.get(name):
        found += count
    return found
