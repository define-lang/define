"""A function that only a test outside the area tests."""

from __future__ import annotations


def is_larger(left: int, right: int) -> bool:
    """Return whether `left` is larger than `right`."""
    return right < left
