"""Linux scheduler-runtime capture for statistical CPU profiling."""

from __future__ import annotations

import pathlib
import typing

if typing.TYPE_CHECKING:
    from tools.profiler import schema


def sampling_configuration(
    base: schema.SamplingConfigurationBase,
) -> schema.CpuSamplingConfiguration:
    """Describe the selected external CPU backend."""
    # PRF-014: CPU mode.
    return {
        **base,
        "mode": "cpu",
        "cpu_backend": "linux-schedstat",
        "python_stack_trampolines": False,
    }


def scheduler_runtimes(process_id: int) -> dict[int, int]:
    """Read cumulative scheduler runtime for each live target thread."""
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    runtimes: dict[int, int] = {}
    for thread_directory in pathlib.Path(f"/proc/{process_id}/task").iterdir():
        schedstat = (thread_directory / "schedstat").read_text(encoding="utf-8")
        runtimes[int(thread_directory.name)] = int(schedstat.split()[0])
    return runtimes
