"""Explicitly released normal-exit fixture for profiler lifecycle tests."""

import sys

# PRF-024: Explicit failures. PRF-049: Event-driven coordination.
with open(sys.argv[1], "rb") as _profiler_gate:
    _ = _profiler_gate.read(1)
