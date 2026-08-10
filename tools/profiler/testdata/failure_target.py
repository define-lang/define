"""Failing process used by profiler integration tests."""

import sys
import time

# PRF-024: Explicit failures. PRF-041: Realistic tests.

time.sleep(0.3)
print("target diagnostic", file=sys.stderr)
raise SystemExit(4)
