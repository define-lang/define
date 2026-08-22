"""Stable process used to interrupt a stopped profiler observation."""

from __future__ import annotations

import threading

# PRF-023: Guaranteed resume. PRF-041: Realistic tests.

_ = threading.Event().wait()
