# Rejected: ruff:PLR6301
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves a method that does not use `self`."""

from __future__ import annotations

from typing import final


@final
class Registry:
    """Values by name."""

    def __init__(self):
        """Start with no values."""
        self._values: dict[str, int] = {}

    def values(self) -> list[int]:
        """Return every value."""
        return _listed(None)


def _listed(values: dict[str, int] | None) -> list[int]:
    return list((values or {}).values())
