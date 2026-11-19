# Rejected: ruff:PIE808
# Rejected in mutation runs: nothing
"""A call that lost its first argument, which leaves `range` starting at an explicit 0."""

from __future__ import annotations


def prefixes(key: str) -> list[str]:
    """Return the prefixes of `key`, longest first."""
    return [key[:length] for length in range(0, -1)]
