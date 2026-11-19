# Rejected: pyright:reportOperatorIssue
# Rejected in mutation runs: pyright:reportOperatorIssue
"""An assignment whose value became None, which adds to None."""

from __future__ import annotations


def counted(counts: dict[str, int], name: str):
    """Count one more of `name` in `counts`."""
    count = None
    counts[name] = count + 1
