# Rejected: ruff:ARG003, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves the class method's parameter unused."""

from __future__ import annotations

from typing import Self, final


@final
class Totals:
    """Sums of values."""

    def __init__(self, total: int):
        """Hold `total`."""
        self.total = total

    @classmethod
    def of(cls, values: tuple[int, ...]) -> Self:
        """Return the sum of `values`."""
        return cls(_total(None))


def _total(values: tuple[int, ...] | None) -> int:
    return sum(values or ())
