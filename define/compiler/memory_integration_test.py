# pyright: reportUnusedCallResult=false
"""End-to-end compiler memory regression test."""

import resource
import subprocess
from pathlib import Path

from define.compiler import test_runfiles

_MEBIBYTE = 1024 * 1024
_MAXIMUM_PEAK_RSS_BYTES = 192 * _MEBIBYTE
_DATA_LIMIT_BYTES = 512 * _MEBIBYTE


def _binary_path() -> Path:
    return test_runfiles.resolve_from_env("MAIN_BINARY")


def _source_path() -> Path:
    return test_runfiles.resolve_from_env("MEMORY_TEST_SOURCE")


def _runner_path() -> Path:
    return test_runfiles.resolve_from_env("MEMORY_LIMIT_RUNNER")


def test_dense_guarantee_expansion_peak_memory():
    source_path = _source_path()
    source = source_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        [
            str(_runner_path()),
            str(_DATA_LIMIT_BYTES),
            str(_binary_path()),
            "validate",
        ],
        input=source,
        capture_output=True,
        check=False,
        text=True,
        cwd=source_path.parent,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr

    peak_rss_bytes = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    assert peak_rss_bytes <= _MAXIMUM_PEAK_RSS_BYTES, (
        f"compiler peak RSS was {peak_rss_bytes / _MEBIBYTE:.1f} MiB; "
        f"limit is {_MAXIMUM_PEAK_RSS_BYTES / _MEBIBYTE:.1f} MiB"
    )
