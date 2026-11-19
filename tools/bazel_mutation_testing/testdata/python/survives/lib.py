"""A function whose test misses its mutant, since it never compares equal values."""

from __future__ import annotations


def is_larger(left: int, right: int) -> bool:
    """Return whether `left` is larger than `right`."""
    return right < left
