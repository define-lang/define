# Rejected: ruff:PLW0120
# Rejected in mutation runs: nothing
"""A `break` that became `return`, which leaves a loop's `else` without a `break`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def record_first_long_name(names: Iterable[str], records: list[str]):
    """Add the first of `names` longer than three characters to `records`, or "" if none is."""
    for name in names:
        if len(name) > 3:
            records.append(name)
            return
    else:
        records.append("")
