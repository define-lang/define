# Rejected: pyright:reportReturnType
# Rejected in mutation runs: pyright:reportReturnType
"""A comparison whose operator was inverted, which returns None where the function does not."""

from __future__ import annotations


def known(names: dict[str, str], name: str) -> str:
    """Return the value of `name`, which must be known."""
    value = names.get(name)
    if value is not None:
        raise KeyError(name)
    return value
