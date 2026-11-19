# Rejected: pyright:reportAttributeAccessIssue, pyright:reportUnknownArgumentType, pyright:reportUnknownMemberType
# Rejected in mutation runs: pyright:reportAttributeAccessIssue, pyright:reportUnknownArgumentType, pyright:reportUnknownMemberType
"""A comparison whose operator was inverted, which reads an attribute of None."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def upper_names(names: Iterable[str | None]) -> list[str]:
    """Return each name that is not None, in capitals."""
    found: list[str] = []
    for name in names:
        if name is not None:
            continue
        found.append(name.upper())
    return found
