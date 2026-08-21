# pyright: reportUnusedCallResult=false
"""End-to-end compiler memory regression test."""

import resource
import subprocess
import typing
from pathlib import Path

import pytest

from define.compiler import test_runfiles

_MEBIBYTE = 1024 * 1024
_MAXIMUM_PEAK_RSS_BYTES = 192 * _MEBIBYTE
_DATA_LIMIT_BYTES = 512 * _MEBIBYTE

type _InputMethod = typing.Literal["stdin", "filesystem"]


def _binary_path() -> Path:
    return test_runfiles.resolve_from_env("MAIN_BINARY")


def _source_path(source_variable: str) -> Path:
    return test_runfiles.resolve_from_env(source_variable)


def _runner_path() -> Path:
    return test_runfiles.resolve_from_env("MEMORY_LIMIT_RUNNER")


@pytest.mark.parametrize(
    ("source_variable", "input_method"),
    [
        pytest.param(
            "MEMORY_TEST_LARGE_OPERATION_VOLUME",
            "stdin",
            id="large_operation_volume",
        ),
        pytest.param(
            "MEMORY_TEST_DESTRUCTION_FRAGMENTS",
            "stdin",
            id="destruction_fragments",
        ),
        pytest.param(
            "MEMORY_TEST_MANY_SUBSTANTIAL_ACTIONS",
            "stdin",
            id="many_substantial_actions",
        ),
        pytest.param(
            "MEMORY_TEST_FRAGMENT_FANOUT_JOINS",
            "stdin",
            id="fragment_fanout_joins",
        ),
        pytest.param(
            "MEMORY_TEST_REFERENCE_GRAPH_PROJECT",
            "filesystem",
            id="reference_graph_project",
        ),
        pytest.param(
            "MEMORY_TEST_OPERATION_DEPENDENCIES",
            "stdin",
            id="operation_dependencies",
        ),
        pytest.param(
            "MEMORY_TEST_GUARANTEE_EXPANSION",
            "stdin",
            id="guarantee_expansion",
        ),
        pytest.param(
            "MEMORY_TEST_DEEP_REQUIREMENTS",
            "stdin",
            id="deep_requirements",
        ),
    ],
)
def test_peak_memory(source_variable: str, input_method: _InputMethod, tmp_path: Path):
    source_path = _source_path(source_variable)
    command = [
        str(_runner_path()),
        str(_DATA_LIMIT_BYTES),
        str(_binary_path()),
        "compile",
        "--max-threads",
        "4",
        "--out",
        str(tmp_path / "generated"),
    ]
    source = None
    if input_method == "filesystem":
        command.append(source_path.name)
    else:
        source = source_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        command,
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
