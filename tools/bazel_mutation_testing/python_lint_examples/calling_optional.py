# Rejected: pyright:reportOptionalCall
# Rejected in mutation runs: pyright:reportOptionalCall
"""A comparison whose operator was inverted, which calls what may be None."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def notified(handler: Callable[[str], None] | None, name: str) -> bool:
    """Call `handler` with `name` if there is a handler, and return whether there was one."""
    if handler is not None:
        return False
    handler(name)
    return True
