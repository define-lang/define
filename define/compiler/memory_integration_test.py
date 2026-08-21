# pyright: reportUnusedCallResult=false
"""End-to-end compiler memory regression test."""

import resource
import subprocess
from pathlib import Path

import pytest

from define.compiler import test_runfiles

_MEBIBYTE = 1024 * 1024
_MAXIMUM_PEAK_RSS_BYTES = 192 * _MEBIBYTE
_DATA_LIMIT_BYTES = 512 * _MEBIBYTE


def _binary_path() -> Path:
    return test_runfiles.resolve_from_env("MAIN_BINARY")


def _source_path(source_variable: str) -> Path:
    return test_runfiles.resolve_from_env(source_variable)


def _runner_path() -> Path:
    return test_runfiles.resolve_from_env("MEMORY_LIMIT_RUNNER")


@pytest.mark.parametrize(
    "source_variable",
    [
        "MEMORY_TEST_LARGE_OPERATION_VOLUME",
        "MEMORY_TEST_DESTRUCTION_FRAGMENTS",
        "MEMORY_TEST_OPERATION_DEPENDENCIES",
        "MEMORY_TEST_GUARANTEE_EXPANSION",
        "MEMORY_TEST_DEEP_REQUIREMENTS",
    ],
    ids=[
        "large_operation_volume",
        "destruction_fragments",
        "operation_dependencies",
        "guarantee_expansion",
        "deep_requirements",
    ],
)
def test_peak_memory(source_variable: str, tmp_path: Path):
    source_path = _source_path(source_variable)
    source = source_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        [
            str(_runner_path()),
            str(_DATA_LIMIT_BYTES),
            str(_binary_path()),
            "compile",
            "--max-threads",
            "4",
            "--out",
            str(tmp_path / "generated"),
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
