# Rejected: ruff:PLW0108
# Rejected in mutation runs: nothing
"""A call whose argument was deleted, which leaves a lambda that passes its parameter straight through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Names:
    """Names that are looked up in a scope."""

    def __init__(self, scope: str):
        """Look up names in `scope`."""
        self._scope = scope

    def checkers(self) -> Callable[[str], str]:
        """Return a function that looks up a name in this scope."""
        return lambda name: self._look_up(name)

    def _look_up(self, name: str, scope: str = "") -> str:
        return f"{scope or self._scope}.{name}"
