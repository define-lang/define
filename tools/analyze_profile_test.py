from __future__ import annotations

from typing import TYPE_CHECKING

import click.testing
import pytest

from tools.profiler import analyzer

if TYPE_CHECKING:
    from pathlib import Path

_CPU_STACKS = (
    "ThreadPoolExecu-10/12;__GI___clone3;start_thread;py::Worker.run:/repo/define/compiler/work.py;"
    + "py::validate:/repo/define/compiler/validate.py;malloc 6\n"
    + "ThreadPoolExecu-10/12;__GI___clone3;start_thread;py::Worker.run:/repo/define/compiler/work.py;"
    + "py::generate:/repo/define/compiler/generate.py 3\n"
    + "python-10/10;_start 1\n"
)


def _analyze_cpu(tmp_path: Path, *arguments: str) -> click.testing.Result:
    profile_path = tmp_path / "stacks.txt"
    _ = profile_path.write_text(_CPU_STACKS, encoding="utf-8", newline="\n")
    return click.testing.CliRunner().invoke(
        analyzer.main, ["--profile", str(profile_path), *arguments]
    )


def test_rejects_a_file_that_is_not_a_profile(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    _ = profile_path.write_text(
        '{"record_type": "header"}\n' * 100, encoding="utf-8", newline="\n"
    )

    result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )

    assert result.exit_code == 1
    assert result.output.startswith("Error: line 1 is not a collapsed stack: ")


def test_help_describes_the_views():
    result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--help"],
        terminal_width=100,
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "--thread" in help_text
    assert "--depth" in help_text
    assert "--focus" in help_text
    assert "--view [timeline|critical-path|functions|tree|callers]" in help_text
    assert "--minimum-run-ms" in help_text
    assert "--start-seconds" in help_text
    assert "prints each thread's runs of work and waiting" in help_text


def test_cpu_profile_defaults_to_the_function_tables(tmp_path: Path):
    result = _analyze_cpu(tmp_path, "--limit", "2")

    assert result.exit_code == 0
    assert result.output == (
        "Profile: Linux perf CPU samples at 997 Hz; times are sampled CPU time; "
        + "0.0% of samples have stacks perf could not unwind to their thread's "
        + "start, which appear under (stack not unwound to its thread's start)\n"
        + "Threads, with the deepest function holding most of each one's time:\n"
        + "     0.009 s  90.0%  12 ThreadPoolExecu: validate\n"
        + "     0.001 s  10.0%  10 python (main): (no Python frame)\n"
        + "\nCumulative:\n"
        + "     0.009 s  90.0%  Worker.run\n"
        + "     0.006 s  60.0%  validate\n"
        + "\nSelf:\n"
        + "     0.006 s  60.0%  validate\n"
        + "     0.003 s  30.0%  generate\n"
    )


def test_cpu_tree_focuses_on_a_function_within_selected_threads(tmp_path: Path):
    result = _analyze_cpu(
        tmp_path, "--view", "tree", "--focus", "generate", "--thread", "12"
    )

    assert result.exit_code == 0
    assert result.output.endswith(
        "\nFocus: stacks from the outermost function containing 'generate'\n"
        + "\nCall tree, with each function's own self time:\n"
        + "     0.003 s  33.3%  self 33.3%  generate\n"
    )


def test_reports_samples_of_other_processes(tmp_path: Path):
    profile_path = tmp_path / "stacks.txt"
    _ = profile_path.write_text(
        _CPU_STACKS + "ldconfig-11/11;_start 1\n", encoding="utf-8", newline="\n"
    )

    result = click.testing.CliRunner().invoke(
        analyzer.main, ["--profile", str(profile_path)]
    )

    assert result.exit_code == 0
    assert result.output.splitlines()[1] == (
        "Left out: samples of other processes perf followed: ldconfig 11 0.001 s"
    )


def test_cpu_native_frames_appear_in_self_time(tmp_path: Path):
    result = _analyze_cpu(tmp_path, "--native", "--limit", "1")

    assert result.exit_code == 0
    assert result.output.endswith("\nSelf:\n     0.006 s  60.0%  malloc\n")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--view", "timeline"], "a CPU profile has no timeline"),
        (["--view", "critical-path"], "a CPU profile has no timeline"),
        (["--start-seconds", "1"], "a CPU profile has no sample times"),
    ],
)
def test_rejects_wall_only_options_for_a_cpu_profile(
    tmp_path: Path, arguments: list[str], message: str
):
    result = _analyze_cpu(tmp_path, *arguments)

    assert result.exit_code == 2
    assert f"Error: {message}" in result.output


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--thread", "99"], "no samples match the selection"),
        (["--focus", "missing"], "no selected stack contains 'missing'"),
    ],
)
def test_reports_an_empty_selection(tmp_path: Path, arguments: list[str], message: str):
    result = _analyze_cpu(tmp_path, *arguments)

    assert result.exit_code == 1
    assert result.stderr == f"Error: {message}\n"


def test_cpu_callers_view(tmp_path: Path):
    result = _analyze_cpu(tmp_path, "--view", "callers", "--focus", "generate")

    assert result.exit_code == 0
    assert result.output.endswith(
        "under the function it calls:\n"
        + "     0.003 s  30.0%  generate\n"
        + "     0.003 s  30.0%    Worker.run\n"
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--view", "callers"], "Error: --view callers needs --focus\n"),
        (
            ["--view", "callers", "--focus", "absent"],
            "Error: no selected stack contains 'absent'\n",
        ),
    ],
)
def test_callers_need_a_function(tmp_path: Path, arguments: list[str], message: str):
    result = _analyze_cpu(tmp_path, *arguments)

    assert result.exit_code != 0
    assert message in result.output
