# Rejected: ruff:TC003
# Rejected in mutation runs: nothing
"""A call whose argument became None, which leaves a standard library import that only annotations use."""

from __future__ import annotations

import threading


def lock_for(
    locks: dict[str, threading.Lock | None], name: str
) -> threading.Lock | None:
    """Return the lock for `name`, which is added if it is missing."""
    return locks.setdefault(name, None)
