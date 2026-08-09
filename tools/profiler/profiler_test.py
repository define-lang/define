import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import click.testing
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.profiler import profiler, schema


def _runfile(variable: str) -> Path:
    location = os.environ[variable]
    candidate = Path(location)
    if candidate.exists():
        return candidate
    runfiles_resolver = runfiles.Runfiles.Create()
    assert runfiles_resolver is not None
    resolved = runfiles_resolver.Rlocation(location)
    assert resolved is not None
    return Path(resolved)


def _profile_command(profile_path: Path) -> list[str]:
    # PRF-020: Machine and human interfaces.
    test_target = _runfile("PROFILER_TEST_TARGET")
    return [
        str(_runfile("PROFILER_BINARY")),
        "--profile",
        str(profile_path),
        "--workload",
        str(test_target),
        "--snapshot-delay-seconds",
        "0.2",
        "--",
        str(test_target),
    ]


# PRF-020: Machine and human interfaces. PRF-041: Realistic tests.
def test_main_profiles_relative_target(tmp_path: Path):
    target_path = tmp_path / "target"
    target_path.symlink_to(sys.executable)
    profile_path = tmp_path / "profile.json"

    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(Path(__file__)),
            "--working-directory",
            str(tmp_path),
            "--snapshot-delay-seconds",
            "0.05",
            "--",
            "./target",
            "-c",
            "import time; time.sleep(0.3)",
        ],
    )

    assert result.exit_code == 0
    profile = schema.load(profile_path)
    assert profile["success"] is True
    assert profile["snapshot"] is not None


# PRF-006: Complete-process stop. PRF-007: Consistent stack.
# PRF-011: Complete invocation.
# PRF-013: Wall mode. PRF-015: Full stacks. PRF-016: Source identity.
# PRF-020: Machine and human interfaces. PRF-021: Version match.
# PRF-022: Launcher safety. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_public_binaries_capture_and_analyze_real_threads(tmp_path: Path):
    profile_path = tmp_path / "profile.json"

    capture_result = subprocess.run(
        _profile_command(profile_path), capture_output=True, text=True, check=False
    )

    assert capture_result.returncode == 0
    assert capture_result.stdout == ""
    assert capture_result.stderr == ""
    profile = schema.load(profile_path)
    assert profile["complete"] is True
    assert profile["success"] is True
    assert profile["python_runtime"] is not None
    assert (
        profile["launcher_executable"]["inode"]
        != profile["python_runtime"]["executable"]["inode"]
    )
    assert profile["python_runtime"]["minor_version"] == "3.14"
    assert profile["python_runtime"]["free_threaded"] is True
    profiler_executable = Path("/proc/self/exe").stat()
    assert (
        profile["python_runtime"]["executable"]["device"],
        profile["python_runtime"]["executable"]["inode"],
    ) == (profiler_executable.st_dev, profiler_executable.st_ino)
    assert profile["snapshot"] is not None
    python_observed_ns = profile["lifecycle"]["python_observed_ns"]
    assert python_observed_ns is not None
    assert (
        profile["lifecycle"]["launched_ns"]
        < python_observed_ns
        <= profile["snapshot"]["host_monotonic_ns"]
        < profile["lifecycle"]["exited_ns"]
    )
    assert len(profile["snapshot"]["threads"]) == 3
    assert all(
        thread["stopped_state"] in {"T", "t"}
        for thread in profile["snapshot"]["threads"]
    )
    assert all(thread["stack"] for thread in profile["snapshot"]["threads"])
    assert profile["snapshot"]["pause_duration_ns"] > 0
    assert profile["snapshot"]["target_running_ns"] > 0
    assert profile["observation_counts"] == {
        "attempted": 1,
        "successful": 1,
        "discarded": 0,
        "missed": 0,
    }
    sampled_functions = {
        frame["function"]
        for thread_snapshot in profile["snapshot"]["threads"]
        for frame in thread_snapshot["stack"]
    }
    assert "_wait_in_first_worker" in sampled_functions
    assert "_wait_in_second_worker" in sampled_functions

    analysis_result = subprocess.run(
        [str(_runfile("ANALYZER_BINARY")), "--profile", str(profile_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert "Snapshot: 3 Python threads" in analysis_result.stdout
    assert "_wait_in_first_worker" in analysis_result.stdout
    assert "_wait_in_second_worker" in analysis_result.stdout


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_normal_exit_before_snapshot_is_an_explicit_failure(tmp_path: Path):
    profile_path = tmp_path / "profile.json"

    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(Path(__file__)),
            "--snapshot-delay-seconds",
            "1",
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
    )

    assert result.exit_code == 1
    assert "Error: profile capture was not successful" in result.output
    profile = schema.load(profile_path)
    assert profile["complete"] is True
    assert profile["success"] is False
    assert profile["snapshot"] is None
    assert profile["observation_counts"] == {
        "attempted": 0,
        "successful": 0,
        "discarded": 0,
        "missed": 1,
    }
    assert profile["failures"][0]["kind"] == "target-exited-before-snapshot"


# PRF-023: Guaranteed resume. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
def test_real_interrupt_resumes_and_terminates_target(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    profile_process = subprocess.Popen(
        _profile_command(profile_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(1.0)

    profile_process.send_signal(signal.SIGTERM)
    stdout, stderr = profile_process.communicate(timeout=10)

    assert profile_process.returncode == 1
    assert stdout == b""
    assert b"Aborted!" in stderr
    profile = schema.load(profile_path)
    assert profile["complete"] is False
    assert profile["success"] is False
    assert profile["interruption_signal"] == signal.SIGTERM
    assert profile["compiler_exit_status"] == -signal.SIGTERM
    assert profile["failures"][-1]["kind"] == "profiler-interrupted"
    assert profile["failures"][-1]["reason"] == "SIGTERM"
    assert profile["snapshot"] is not None
    target_process_id = profile["snapshot"]["process_id"]
    assert not Path(f"/proc/{target_process_id}").exists()


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_capture_records_diagnostics_and_nonzero_exit(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    test_target = _runfile("PROFILER_FAILURE_TARGET")

    profile = profiler.capture(
        command=(str(test_target),),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        snapshot_delay_seconds=0.1,
        attachment_timeout_seconds=5.0,
    )

    assert profile["success"] is False
    assert profile["diagnostics_status"] == "present"
    assert profile["compiler_exit_status"] == 4
    assert json.loads(profile_path.read_text(encoding="utf-8")) == profile


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_main_handles_a_real_signal_in_the_calling_process(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    test_target = _runfile("PROFILER_TEST_TARGET")

    def interrupt_capture() -> None:
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

    interrupt_thread = threading.Thread(target=interrupt_capture)
    interrupt_thread.start()
    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(Path(__file__)),
            "--working-directory",
            str(tmp_path),
            "--snapshot-delay-seconds",
            "1",
            "--",
            str(test_target),
        ],
    )
    interrupt_thread.join()

    assert result.exit_code == 1
    assert "Aborted!" in result.output
    profile = schema.load(profile_path)
    assert profile["complete"] is False
    assert profile["snapshot"] is None
    assert profile["interruption_signal"] == signal.SIGINT
    assert profile["compiler_exit_status"] == -signal.SIGTERM


# PRF-022: Launcher safety. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
def test_attachment_timeout_terminates_non_python_target(tmp_path: Path):
    profile_path = tmp_path / "profile.json"

    profile = profiler.capture(
        command=("/bin/sleep", "1"),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        snapshot_delay_seconds=0.1,
        attachment_timeout_seconds=0.05,
    )

    assert profile["success"] is False
    assert profile["python_runtime"] is None
    assert profile["compiler_exit_status"] == -signal.SIGTERM
    assert profile["failures"][0]["kind"] == "attachment-timeout"


# PRF-022: Launcher safety. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
def test_non_python_target_exit_before_attachment_is_recorded(tmp_path: Path):
    profile_path = tmp_path / "profile.json"

    profile = profiler.capture(
        command=("/bin/sleep", "0.05"),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        snapshot_delay_seconds=0.1,
        attachment_timeout_seconds=1.0,
    )

    assert profile["success"] is False
    assert profile["python_runtime"] is None
    assert profile["compiler_exit_status"] == 0
    assert profile["failures"][0]["kind"] == "target-exited-before-snapshot"
