# Rejected: pyright:reportOptionalOperand
# Rejected in mutation runs: pyright:reportOptionalOperand
"""A call that lost its default, which adds to what may be None."""

from __future__ import annotations


def counted(counts: dict[str, int], name: str):
    """Count one more of `name` in `counts`."""
    counts[name] = counts.get(name) + 1
