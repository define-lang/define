# Rejected: ruff:SIM222
# Rejected in mutation runs: nothing
"""A conditional expression whose condition was forced true."""

from __future__ import annotations


def label(name: str | None) -> str | None:
    """Return the label of `name`, or None if there is no name."""
    return None if (name is None) or True else name.upper()
