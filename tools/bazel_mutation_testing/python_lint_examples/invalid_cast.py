# Rejected: pyright:reportInvalidCast
# Rejected in mutation runs: pyright:reportInvalidCast
"""A comparison whose operator was inverted, which casts None to a type that cannot be None."""

from __future__ import annotations

import typing


def first_name(names: dict[str, object]) -> str | None:
    """Return the name that `names` holds under "first", if it holds one."""
    found = names.get("first")
    if found is not None:
        return None
    return typing.cast("str", found)
