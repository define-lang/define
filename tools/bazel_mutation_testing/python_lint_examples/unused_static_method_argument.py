# Rejected: ruff:ARG004, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves the static method's parameter unused."""

from __future__ import annotations

from typing import final


@final
class Totals:
    """Sums of values."""

    @staticmethod
    def total(values: tuple[int, ...]) -> int:
        """Return the sum of `values`."""
        return _total(None)


def _total(values: tuple[int, ...] | None) -> int:
    return sum(values or ())
