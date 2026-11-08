from __future__ import annotations

import multiprocessing
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import click.testing
import pytest

from tools import runfiles
from tools.profiler import analyzer, tachyon_profile, tachyon_profiler, wall_timeline

if TYPE_CHECKING:
    from pathlib import Path


def _release_phases(status_path: Path, control_path: Path, phases: bytes):
    with (
        status_path.open("rb", buffering=0) as status_stream,
        control_path.open("wb", buffering=0) as control_stream,
    ):
        for phase in phases:
            assert status_stream.read(1) == bytes([phase])
            _ = control_stream.write(b"1")


def _capture(profile_path: Path, *command: str) -> int:
    return tachyon_profiler.capture(
        command=command,
        profile_path=profile_path,
        working_directory=profile_path.parent,
        environment=dict(os.environ),
        stdin=None,
    )


def _analyze(profile_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            str(runfiles.resolve_from_env("ANALYZER_BINARY")),
            "--profile",
            str(profile_path),
            "--limit",
            "25",
            *arguments,
        ),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no FIFOs")
def test_captures_and_analyzes_a_threaded_target(tmp_path: Path):
    profile_path = tmp_path / "profile.bin"
    status_path = tmp_path / "status"
    control_path = tmp_path / "control"
    os.mkfifo(status_path)
    os.mkfifo(control_path)
    # A process can be stopped if capture fails before the target opens its FIFOs.
    releaser = multiprocessing.get_context("spawn").Process(
        target=_release_phases, args=(status_path, control_path, b"1234")
    )
    releaser.start()
    try:
        exit_status = _capture(
            profile_path,
            sys.executable,
            str(runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_SOURCE")),
            str(status_path),
            str(control_path),
        )
        releaser.join(timeout=10)
        assert releaser.exitcode == 0
    finally:
        if releaser.is_alive():
            releaser.terminate()
        releaser.join()
        releaser.close()

    assert exit_status == 0
    analysis = _analyze(profile_path)
    assert analysis.returncode == 0
    assert analysis.stderr == ""
    assert "Profile: Tachyon wall samples" in analysis.stdout
    assert " (main): " in analysis.stdout
    # Every main-thread stack starts at the target, not at the frames that
    # launch it.
    assert "_sync_coordinator" not in analysis.stdout
    assert "tachyon_target" not in analysis.stdout


def test_capture_returns_the_targets_exit_status(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
):
    exit_gate = tmp_path / "exit-gate"
    _ = exit_gate.write_bytes(b"1")

    exit_status = _capture(
        tmp_path / "failure.bin",
        sys.executable,
        str(runfiles.resolve_from_env("PROFILER_FAILURE_SOURCE")),
        str(exit_gate),
    )

    assert exit_status == 4
    assert capfd.readouterr().err.splitlines() == ["target diagnostic"]


def test_capture_runs_the_script_behind_a_bazel_python_binary(tmp_path: Path):
    exit_gate = tmp_path / "exit-gate"
    _ = exit_gate.write_bytes(b"1")

    exit_status = _capture(
        tmp_path / "profile.bin",
        str(runfiles.resolve_from_env("PROFILER_FAILURE_BINARY")),
        str(exit_gate),
    )

    assert exit_status == 4


def test_capture_requires_a_python_script(tmp_path: Path):
    with pytest.raises(
        tachyon_profiler.CaptureError,
        match="^the command must be a Bazel Python binary or a Python interpreter "
        + "followed by a script$",
    ):
        _ = _capture(tmp_path / "profile.bin", sys.executable)


def test_timeline_shows_each_stage_of_a_cross_thread_chain():
    profile = tachyon_profile.load(
        runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_PROFILE")
    )

    runs_by_thread = wall_timeline.thread_runs(
        profile,
        wall_timeline.TimelineOptions(depth=2, minimum_run_ns=20_000_000),
    )

    # The fixture runs four stages one after another, each on its own thread and
    # the last on the main thread, while another thread works throughout.
    stage_runs = sorted(
        (run.start_ns, thread_id)
        for thread_id, runs in runs_by_thread.items()
        for run in runs
        if run.path == ("[_controlled_work]",) and run.working_ns > run.duration_ns // 2
    )
    assert len(stage_runs) == 4
    assert len({thread_id for _, thread_id in stage_runs}) == 4
    assert stage_runs[-1][1] == profile.main_thread_id
    assert any(
        run.path == ("[_off_path_work]",) and run.duration_ns > 150_000_000
        for runs in runs_by_thread.values()
        for run in runs
    )

    analysis = _analyze(runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_PROFILE"))
    assert analysis.returncode == 0
    assert analysis.stderr == ""
    assert f"\nThread {profile.main_thread_id} (main): " in analysis.stdout
    assert "  work  [_controlled_work]\n" in analysis.stdout


def test_function_views_cover_the_selected_part_of_a_wall_profile():
    profile_path = runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_PROFILE")
    main_thread_id = tachyon_profile.load(profile_path).main_thread_id
    runner = click.testing.CliRunner()

    functions = runner.invoke(
        analyzer.main,
        [
            "--profile",
            str(profile_path),
            "--view",
            "functions",
            "--thread",
            str(main_thread_id),
        ],
    )
    tree = runner.invoke(
        analyzer.main,
        [
            "--profile",
            str(profile_path),
            "--view",
            "tree",
            "--focus",
            "_stage_two_worker",
        ],
    )

    assert functions.exit_code == 0
    assert f"  {main_thread_id} (main): " in functions.output
    assert "\nCumulative:\n" in functions.output
    assert "  <module critical_path_target.py>\n" in functions.output
    assert tree.exit_code == 0
    tree_lines = tree.output.split(
        "\nCall tree, with each function's own self time:\n"
    )[1].splitlines()
    assert tree_lines[0].endswith("  _stage_two_worker")


def test_critical_path_follows_each_stage_of_the_chain():
    profile_path = runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_PROFILE")

    result = click.testing.CliRunner().invoke(
        analyzer.main, ["--profile", str(profile_path), "--view", "critical-path"]
    )

    assert result.exit_code == 0
    assert result.output.count("  [_controlled_work]\n") >= 4
    assert "  thread main  " in result.output


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            ("--view", "critical-path", "--thread", "1"),
            "the critical path follows every thread",
        ),
        (("--native",), "--native applies only to CPU profiles"),
        (("--focus", "stage"), "--focus applies only to functions and tree"),
    ],
)
def test_rejects_cpu_only_and_function_only_options_for_a_timeline(
    arguments: tuple[str, ...], message: str
):
    analysis = _analyze(
        runfiles.resolve_from_env("PROFILER_CRITICAL_PATH_PROFILE"), *arguments
    )

    assert analysis.returncode == 2
    assert f"Error: {message}" in analysis.stderr
