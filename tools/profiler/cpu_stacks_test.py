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


def test_keeps_native_frames_below_the_innermost_python_frame(tmp_path: Path):
    profile_path = _write(
        tmp_path,
        "python-10/10;_start;py::Driver.run:/repo/define/driver.py;"
        + "_PyEval_EvalFrameDefault;py::check:/repo/define/check.py;"
        + "_PyEval_EvalFrameDefault;malloc 1\n"
        + "python-10/11;__GI___clone3;start_thread 1\n",
    )

    loaded = cpu_stacks.load(profile_path, native=True)

    assert [stack.functions for stack in loaded.stacks] == [
        ("Driver.run", "check", "_PyEval_EvalFrameDefault", "malloc"),
        ("__GI___clone3", "start_thread"),
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


def test_leaves_out_processes_other_than_the_compiler(tmp_path: Path):
    loaded = cpu_stacks.load(
        _write(tmp_path, "python-10/10;_start 2\nldconfig-11/11;_start 1\n"),
        native=False,
    )

    assert loaded.main_thread_id == 10
    assert loaded.thread_names == {10: "python"}
    assert loaded.other_processes == {"ldconfig 11": 1_003_009}


def test_a_main_thread_stack_may_end_at_the_python_entry(tmp_path: Path):
    loaded = cpu_stacks.load(
        _write(tmp_path, "python-10/10;pymain_main 1\npython-10/10;Py_Main 1\n"),
        native=False,
    )

    assert loaded.truncated_ns == 1_003_009
