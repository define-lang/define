from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.profiler import call_tree, cpu_stacks

if TYPE_CHECKING:
    from pathlib import Path

_SAMPLE_NS = round(1_000_000_000 / cpu_stacks.SAMPLING_FREQUENCY_HZ)


def _write(tmp_path: Path, text: str) -> Path:
    profile_path = tmp_path / "stacks.txt"
    _ = profile_path.write_text(text, encoding="utf-8", newline="\n")
    return profile_path


def test_loads_python_frames_and_thread_names(tmp_path: Path):
    profile_path = _write(
        tmp_path,
        "ThreadPoolExecu-10/12;start_thread;py::<module>:/repo/define/main.py;"
        + "py::_find_and_load:<frozen importlib._bootstrap>;"
        + "_PyEval_Vector;py::Driver.run:/repo/define/driver.py;malloc 3\n"
        + "target-launcher-10/10;_start;py::<module>:<string> 1\n"
        + "python-10/10;_start;exit 2\n",
    )

    loaded = cpu_stacks.load(profile_path, native=False)

    assert loaded.thread_names == {12: "ThreadPoolExecu", 10: "python"}
    assert loaded.main_thread_id == 10
    # The worker's stack starts at start_thread, below where perf lost it.
    assert loaded.truncated_ns == 3 * _SAMPLE_NS
    assert loaded.stacks == [
        call_tree.WeightedStack(
            thread_id=12,
            functions=(cpu_stacks.NOT_UNWOUND, "<module main.py>", "Driver.run"),
            total_ns=3 * _SAMPLE_NS,
            working_ns=3 * _SAMPLE_NS,
        ),
        call_tree.WeightedStack(
            thread_id=10,
            functions=("<module <string>>",),
            total_ns=_SAMPLE_NS,
            working_ns=_SAMPLE_NS,
        ),
        call_tree.WeightedStack(
            thread_id=10,
            functions=(),
            total_ns=2 * _SAMPLE_NS,
            working_ns=2 * _SAMPLE_NS,
        ),
    ]


def test_keeps_native_frames_when_requested(tmp_path: Path):
    profile_path = _write(
        tmp_path, "python-10/10;_start;py::Driver.run:/repo/define/driver.py;malloc 1\n"
    )

    loaded = cpu_stacks.load(profile_path, native=True)

    assert [stack.functions for stack in loaded.stacks] == [
        ("_start", "Driver.run", "malloc")
    ]


def test_rejects_a_profile_without_stacks(tmp_path: Path):
    with pytest.raises(ValueError, match=r"^profile contains no stacks$"):
        _ = cpu_stacks.load(_write(tmp_path, ""), native=False)


def test_rejects_a_line_that_is_not_a_collapsed_stack(tmp_path: Path):
    with pytest.raises(
        ValueError, match=r"^line 2 is not a collapsed stack: python-10/10;main many$"
    ):
        _ = cpu_stacks.load(
            _write(tmp_path, "python-10/10;main 1\npython-10/10;main many\n"),
            native=False,
        )


def test_rejects_stacks_from_more_than_one_process(tmp_path: Path):
    with pytest.raises(
        ValueError, match=r"^profile does not contain exactly one process$"
    ):
        _ = cpu_stacks.load(
            _write(tmp_path, "python-10/10;_start 1\nsh-11/11;_start 1\n"), native=False
        )
