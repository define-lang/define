# Rejected: pyright:reportMatchNotExhaustive, pyright:reportUnusedFunction
# Rejected in mutation runs: nothing
"""A match whose case was removed, which leaves the helper that only it called."""

from __future__ import annotations


def record(value: int | str, records: list[str]):
    """Add a record of `value` to `records`."""
    match value:
        case str():
            records.append(value)


def _record_number(value: int, records: list[str]):
    records.append(str(value))
