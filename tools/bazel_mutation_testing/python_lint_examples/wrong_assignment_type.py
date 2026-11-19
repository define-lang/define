# Rejected: pyright:reportAssignmentType
# Rejected in mutation runs: pyright:reportAssignmentType
"""An annotated assignment whose value became None, which its type does not allow."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def doubled(values: Iterable[int]) -> list[int]:
    """Return each of `values` doubled."""
    found: list[int] = None
    found.extend(value * 2 for value in values)
    return found
