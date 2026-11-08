"""Run a Python script and count how many times each function starts.

Usage: call_count_target.py COUNTS_FILE STATUS_FILE SCRIPT [ARGUMENT...]

Writes the counts to COUNTS_FILE as JSON, keyed by each function's qualified
name and file, and the script's exit status to STATUS_FILE.
"""

from __future__ import annotations

import collections
import json
import pathlib
import runpy
import sys
import threading
import typing

if typing.TYPE_CHECKING:
    import types

_counts_path = pathlib.Path(sys.argv[1])
_status_path = pathlib.Path(sys.argv[2])
_script = sys.argv[3]
sys.argv = sys.argv[3:]

_TOOL = sys.monitoring.PROFILER_ID
# Each thread counts into its own counter, so threads do not contend on one.
_thread_counts = threading.local()
_all_counts: list[collections.Counter[types.CodeType]] = []
_all_counts_lock = threading.Lock()


def _count_start(code: types.CodeType, _offset: int):
    counts: collections.Counter[types.CodeType] | None = getattr(
        _thread_counts, "counts", None
    )
    if counts is None:
        counts = collections.Counter()
        _thread_counts.counts = counts
        with _all_counts_lock:
            _all_counts.append(counts)
    counts[code] += 1


def _write_counts():
    totals: collections.Counter[tuple[str, str]] = collections.Counter()
    for counts in _all_counts:
        for code, count in counts.items():
            totals[(code.co_qualname, code.co_filename)] += count
    calls: list[dict[str, str | int]] = []
    for (function, filename), count in totals.items():
        calls.append({"function": function, "filename": filename, "calls": count})
    _ = _counts_path.write_text(
        json.dumps({"calls": calls}), encoding="utf-8", newline="\n"
    )


sys.monitoring.use_tool_id(_TOOL, "define call counter")
_ = sys.monitoring.register_callback(
    _TOOL, sys.monitoring.events.PY_START, _count_start
)
sys.monitoring.set_events(_TOOL, sys.monitoring.events.PY_START)
_status = 1
try:
    _ = runpy.run_path(_script, run_name="__main__")
    _status = 0
except SystemExit as exit_request:
    if exit_request.code is None:
        _status = 0
    elif isinstance(exit_request.code, int):
        _status = exit_request.code
    raise
finally:
    sys.monitoring.set_events(_TOOL, 0)
    _write_counts()
    _ = _status_path.write_text(str(_status), encoding="utf-8", newline="\n")
