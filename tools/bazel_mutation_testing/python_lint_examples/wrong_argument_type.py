# Rejected: pyright:reportArgumentType
# Rejected in mutation runs: pyright:reportArgumentType
"""A call whose argument became None, which the function does not accept."""

from __future__ import annotations


def heading(name: str) -> str:
    """Return `name` padded to a heading's width."""
    return _padded(name, None)


def _padded(text: str, width: int) -> str:
    return text.ljust(width)
