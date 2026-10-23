"""Check that this machine lets the profiler record what each mode needs."""

from __future__ import annotations

import os
import pathlib
import shutil

_PARANOID_PATH = pathlib.Path("/proc/sys/kernel/perf_event_paranoid")
_PARANOID_COMMANDS = (
    "  echo 'kernel.perf_event_paranoid = -1' "
    "| sudo tee /etc/sysctl.d/90-perf-profiling.conf\n"
    "  sudo sysctl --system"
)


class PerfAccessError(Exception):
    """The machine does not let the profiler record what its mode needs."""


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
    _require_paranoid_at_most(1, "CPU mode records kernel samples")


def require_scheduler_access(
    trace_roots: tuple[pathlib.Path, ...], tracepoint_names: tuple[str, ...]
):
    """Require the access that wall mode needs to record scheduler tracepoints.

    The tracepoints are `tracepoint_names` in the first of `trace_roots` that
    exists.
    """
    _ = perf_executable()
    _require_paranoid_at_most(-1, "Wall mode records scheduler tracepoints")
    for trace_root in trace_roots:
        try:
            tracepoints_exist = _read_tracepoint_ids(trace_root, tracepoint_names)
        except PermissionError:
            group = os.getgid()
            raise PerfAccessError(
                f"Wall mode reads the scheduler tracepoints in {trace_root}, which "
                + "the current user cannot read. To let your group read them, add "
                + "this line to /etc/fstab:\n"
                + f"  tracefs /sys/kernel/tracing tracefs defaults,gid={group},"
                + "mode=0750 0 0\n"
                + "and then run:\n"
                + "  sudo systemctl daemon-reload\n"
                + f"  sudo mount -o remount,gid={group},mode=0750 /sys/kernel/tracing"
            ) from None
        if tracepoints_exist:
            return
    raise PerfAccessError(
        "Wall mode records scheduler tracepoints, but this kernel does not expose "
        + "them in any of: "
        + ", ".join(str(trace_root) for trace_root in trace_roots)
    )


def _read_tracepoint_ids(
    trace_root: pathlib.Path, tracepoint_names: tuple[str, ...]
) -> bool:
    """Return whether every tracepoint exists, after reading each one's ID."""
    try:
        for tracepoint_name in tracepoint_names:
            _ = (trace_root / tracepoint_name / "id").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return True


def _require_paranoid_at_most(level: int, purpose: str):
    paranoid = int(_PARANOID_PATH.read_text(encoding="utf-8"))
    if paranoid > level:
        raise PerfAccessError(
            f"{purpose}, which needs kernel.perf_event_paranoid set to {level} or "
            + f"lower, but it is {paranoid}. To set it to -1, which every profiler "
            + "mode allows, run:\n"
            + _PARANOID_COMMANDS
        )
