"""Event-controlled failing process used by profiler integration tests."""

from __future__ import annotations

import sys

# PRF-024: Explicit failures. PRF-041: Realistic tests.

with open(sys.argv[1], "rb") as _exit_gate:
    _ = _exit_gate.read(1)
print("target diagnostic", file=sys.stderr)
raise SystemExit(4)
