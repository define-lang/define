# Rejected: ruff:ARG002, pyright:reportUnusedParameter
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves the method's parameter unused."""

from __future__ import annotations

from typing import final


@final
class Totals:
    """Sums of values."""

    def __init__(self, start: int):
        """Start each sum at `start`."""
        self._start = start

    def total(self, values: tuple[int, ...]) -> int:
        """Return the sum of `values`, after the start."""
        return self._start + _total(None)


def _total(values: tuple[int, ...] | None) -> int:
    return sum(values or ())
