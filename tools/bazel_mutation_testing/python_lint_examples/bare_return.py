# Rejected: ruff:RET502, pyright:reportReturnType
# Rejected in mutation runs: pyright:reportReturnType
"""A `break` that became `return`, which returns None from a function that returns a value."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def first_long_name(names: Iterable[str]) -> str:
    """Return the first of `names` longer than three characters, or "" if none is."""
    found = ""
    for name in names:
        if len(name) > 3:
            found = name
            return
    return found
