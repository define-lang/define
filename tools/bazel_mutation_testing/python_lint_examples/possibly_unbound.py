# Rejected: pyright:reportMatchNotExhaustive, pyright:reportPossiblyUnboundVariable
# Rejected in mutation runs: pyright:reportPossiblyUnboundVariable
"""A match whose case was removed, which leaves a variable unbound when no case matches."""

from __future__ import annotations


def label(value: int | str | None) -> str:
    """Return a label for `value`."""
    match value:
        case None:
            return "none"
        case int():
            found = str(value)
    return found
