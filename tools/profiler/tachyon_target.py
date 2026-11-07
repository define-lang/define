"""Run a Python script under Tachyon and record how it exits.

Usage: tachyon_target.py STATUS_FILE SCRIPT [ARGUMENT...]

Tachyon exits successfully whatever its target does, so this records the
script's exit status in STATUS_FILE for the profiler to report.
"""

from __future__ import annotations

import pathlib
import runpy
import sys

_status_path = pathlib.Path(sys.argv[1])
_script = sys.argv[2]
sys.argv = sys.argv[2:]
# Tachyon starts its coordinator with `python -m`, which puts the working
# directory on sys.path, and then puts this file's directory before it. Run the
# script as `python -I` would, without either, so that the target imports only
# what its own environment provides rather than source files in the working
# directory, and a module beside it cannot shadow a standard-library module.
sys.path.remove(str(pathlib.Path(__file__).resolve().parent))
sys.path.remove(str(pathlib.Path.cwd()))
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
    _ = _status_path.write_text(str(_status), encoding="utf-8", newline="\n")
