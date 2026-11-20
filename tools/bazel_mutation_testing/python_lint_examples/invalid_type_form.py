# Rejected: pyright:reportInvalidTypeForm
# Rejected in mutation runs: pyright:reportInvalidTypeForm
"""A type parameter's bound whose union operator was changed, which is not a type."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def first_name[NameT: str & bytes](names: Sequence[NameT]) -> NameT:
    """Return the first of `names`."""
    return names[0]
