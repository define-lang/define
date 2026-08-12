"""Linux scheduler-runtime capture for statistical CPU profiling."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import pathlib

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
    }


def scheduler_runtime(thread_directory: pathlib.Path) -> int:
    """Read one thread's cumulative scheduler runtime."""
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    # PRF-050: Minimal stopped section.
    schedstat = (thread_directory / "schedstat").read_text(encoding="utf-8")
    return int(schedstat.split()[0])
