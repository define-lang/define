# Rejected: ruff:SIM112
# Rejected in mutation runs: nothing
"""An environment variable name whose letters became lowercase."""

from __future__ import annotations

import os


def trace_file() -> str | None:
    """Return the file that the trace is written to, if one is set."""
    return os.environ.get("define_trace_file")
