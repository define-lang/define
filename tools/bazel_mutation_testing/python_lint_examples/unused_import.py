# Rejected: ruff:F401, pyright:reportUnusedImport
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves an import unused."""

from __future__ import annotations

import threading
from typing import final


@final
class Guarded:
    """A value that one thread at a time changes."""

    def __init__(self):
        """Start with no value."""
        self._lock = None
