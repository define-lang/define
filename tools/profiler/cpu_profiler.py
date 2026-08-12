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


def capture_scheduler_runtime(thread_directory: pathlib.Path) -> bytes:
    """Copy one thread's cumulative scheduler-runtime record."""
    # PRF-010: Raw-data preservation. PRF-014: CPU mode.
    # PRF-050: Minimal stopped section.
    return (thread_directory / "schedstat").read_bytes()


def decode_scheduler_runtime(schedstat: bytes) -> int:
    """Decode a copied scheduler-runtime record."""
    # PRF-014: CPU mode. PRF-050: Minimal stopped section.
    return int(schedstat.split(maxsplit=1)[0])
