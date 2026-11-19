# Rejected: pyright:reportCallIssue, pyright:reportUnknownVariableType
# Rejected in mutation runs: pyright:reportCallIssue, pyright:reportUnknownVariableType
"""A call that lost an argument the function requires."""

from __future__ import annotations


def joined(first: str, second: str) -> str:
    """Return `first` and `second` joined by a dot."""
    return _join(first, second)


def _join(first: str, second: str, separator: str) -> str:
    return first + separator + second
