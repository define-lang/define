"""A function with a mutant that only lints that mutation runs turn off reject."""

from __future__ import annotations


def label(name: str) -> str:
    """Return the label of `name`, which is `name` in capitals."""
    upper = name.upper()
    # Passing None instead of `upper` leaves `upper` unused.
    return _label(name, upper)


def _label(name: str, upper: str | None) -> str:
    return upper or name
