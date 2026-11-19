# Rejected: pyright:reportOptionalMemberAccess
# Rejected in mutation runs: pyright:reportOptionalMemberAccess
"""A call that lost its default, which reads an attribute of what may be None."""

from __future__ import annotations


def upper_name(names: dict[str, str], key: str) -> str:
    """Return the name under `key`, in capitals."""
    return names.get(key).upper()
