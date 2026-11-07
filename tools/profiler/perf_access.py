"""Check that this machine lets Linux perf record CPU samples."""

from __future__ import annotations

import pathlib
import shutil

_PARANOID_PATH = pathlib.Path("/proc/sys/kernel/perf_event_paranoid")
_PARANOID_COMMANDS = (
    "  echo 'kernel.perf_event_paranoid = -1' "
    "| sudo tee /etc/sysctl.d/90-perf-profiling.conf\n"
    "  sudo sysctl --system"
)


class PerfAccessError(Exception):
    """The machine does not let Linux perf record CPU samples."""


def perf_executable() -> str:
    """Return the path of Linux perf."""
    executable = shutil.which("perf")
    if executable is None:
        raise PerfAccessError(
            "Linux perf is not installed or not on PATH. Install it, for example "
            + "with `sudo dnf install perf`."
        )
    return executable


def require_cpu_access():
    """Require the access that CPU mode needs to record kernel samples."""
    paranoid = int(_PARANOID_PATH.read_text(encoding="utf-8"))
    if paranoid > 1:
        raise PerfAccessError(
            "CPU mode records kernel samples, which needs "
            + "kernel.perf_event_paranoid set to 1 or lower, but it is "
            + f"{paranoid}. To set it to -1, run:\n"
            + _PARANOID_COMMANDS
        )
