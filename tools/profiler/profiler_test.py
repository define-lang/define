import os
import re
import signal
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import click.testing
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.profiler import (
    analyzer,
    analyzer_model,
    cpu_analyzer,
    profiler,
    schema,
    wall_analyzer,
)


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


def _target_command(source_variable: str) -> tuple[str, ...]:
    source = _runfile(source_variable)
    return (
        "/bin/sh",
        "-c",
        'sleep 0.05; exec "$1" "$2"',
        "profiler-test-launcher",
        sys.executable,
        str(source),
    )


def _profile_command(
    profile_path: Path,
    source_variable: str,
    *,
    mode: schema.CaptureMode = "wall",
    mean_interval_seconds: float = 0.0001,
) -> list[str]:
    # PRF-002: Independent sampling schedule. PRF-020: Machine and human interfaces.
    source = _runfile(source_variable)
    return [
        str(_runfile("PROFILER_BINARY")),
        "--mode",
        mode,
        "--profile",
        str(profile_path),
        "--workload",
        str(source),
        "--mean-interval-seconds",
        str(mean_interval_seconds),
        "--",
        *_target_command(source_variable),
    ]


def _observed_process_id(profile_path: Path) -> int | None:
    try:
        profile_text = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    process_id_match = re.search(r'"process_id":(\d+)', profile_text)
    return int(process_id_match.group(1)) if process_id_match is not None else None


def _wait_for_successful_observation_records(
    profile_path: Path,
    minimum: int,
) -> bool:
    # PRF-027: Incremental persistence. PRF-041: Realistic tests.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            profile_text = profile_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            profile_text = ""
        if profile_text.count('"status":"successful"') >= minimum:
            return True
        time.sleep(0.001)
    return False


def _capture(
    tmp_path: Path,
    source_variable: str,
    *,
    mean_interval_seconds: float = 0.01,
    random_seed: int = 7,
    mode: schema.CaptureMode = "wall",
) -> schema.RawProfile:
    source = _runfile(source_variable)
    return profiler.capture(
        command=_target_command(source_variable),
        profile_path=tmp_path / f"{source_variable}-{random_seed}.jsonl",
        workload_path=source,
        working_directory=tmp_path,
        mean_interval_seconds=mean_interval_seconds,
        random_seed=random_seed,
        attachment_timeout_seconds=5.0,
        mode=mode,
    )


def _assert_recorded_observations(
    observations: list[schema.Observation],
) -> tuple[list[schema.SuccessfulObservation], int]:
    successful: list[schema.SuccessfulObservation] = []
    discarded = 0
    for observation in observations:
        if observation["status"] == "successful":
            successful.append(observation)
        else:
            assert observation["status"] == "discarded"
            assert observation["failure_kind"]
            assert observation["failure_reason"]
            discarded += 1
    return successful, discarded


def _assert_observations_through_exit(
    profile: schema.RawProfile,
) -> tuple[list[schema.SuccessfulObservation], int, int]:
    observations = profile.observations
    if observations[-1]["status"] == "missed":
        successful, discarded = _assert_recorded_observations(observations[:-1])
        return successful, discarded, 1
    successful, discarded = _assert_recorded_observations(observations)
    return successful, discarded, 0


def _sampled_functions(
    profile: schema.RawProfile,
    observations: list[schema.SuccessfulObservation],
) -> set[str]:
    return {
        profile.frames[frame_id]["function"]
        for observation in observations
        for thread in observation["threads"]
        for frame_id in thread["stack"]
    }


# PRF-020: Machine and human interfaces. PRF-041: Realistic tests.
def test_main_profiles_relative_target(tmp_path: Path):
    target_path = tmp_path / "target"
    target_path.symlink_to(sys.executable)
    profile_path = tmp_path / "profile.jsonl"

    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(Path(__file__)),
            "--working-directory",
            str(tmp_path),
            "--mean-interval-seconds",
            "0.01",
            "--",
            "./target",
            "-c",
            "import time; time.sleep(0.15)",
        ],
    )

    assert result.exit_code == 0
    profile = schema.load(profile_path)
    assert profile.success is True
    assert profile.observation_counts["successful"] > 5
    assert profile.sampling["schedule"] == "poisson"


# PRF-002: Independent sampling schedule. PRF-039: Current design only.
def test_help_hides_internal_sampling_parameters():
    result = click.testing.CliRunner().invoke(profiler.main, ["--help"])

    assert result.exit_code == 0
    assert "--mean-interval-seconds" in result.output
    assert "--jitter" not in result.output
    assert "--no-jitter" not in result.output
    assert "--jitter-fraction" not in result.output
    assert "--random-seed" not in result.output


# PRF-002: Independent sampling schedule. PRF-003: Pause exclusion.
# PRF-005: Lifecycle-bounded attribution. PRF-006: Complete-process stop.
# PRF-007: Consistent stack. PRF-011: Complete invocation.
# PRF-013: Wall mode. PRF-015: Full stacks. PRF-016: Source identity.
# PRF-020: Machine and human interfaces. PRF-021: Version match.
# PRF-022: Launcher safety. PRF-025: Failure threshold.
# PRF-027: Incremental persistence. PRF-028: Bounded storage.
# PRF-029: Call-frequency fixture. PRF-030: Stack-depth fixture.
# PRF-031: Retired-thread fixture. PRF-033: Waiting-thread fixture.
# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
def test_public_binaries_capture_and_analyze_continuous_threads(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"

    capture_result = subprocess.run(
        _profile_command(profile_path, "PROFILER_CONTINUOUS_SOURCE"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert capture_result.returncode == 0
    assert capture_result.stdout == ""
    assert capture_result.stderr == ""
    profile = schema.load(profile_path)
    assert profile.complete is True
    assert profile.success is True
    assert profile.sampling["schedule"] == "poisson"
    assert isinstance(profile.sampling["random_seed"], int)
    assert profile.python_runtime is not None
    assert (
        profile.launcher_executable["inode"]
        != profile.python_runtime["executable"]["inode"]
    )
    profiler_executable = Path("/proc/self/exe").stat()
    assert (
        profile.python_runtime["executable"]["device"],
        profile.python_runtime["executable"]["inode"],
    ) == (profiler_executable.st_dev, profiler_executable.st_ino)
    observations, discarded, missed = _assert_observations_through_exit(profile)
    assert len(observations) > 2000
    assert profile.observation_counts == {
        "attempted": len(observations) + discarded,
        "successful": len(observations),
        "discarded": discarded,
        "missed": missed,
    }
    assert profile.sampling_statistics is not None
    assert profile.sampling_statistics["discarded_rate"] <= 0.001
    assert profile.sampling_statistics["total_pause_ns"] == sum(
        observation["pause_duration_ns"] for observation in profile.observations
    )
    assert (
        len({observation["scheduled_interval_ns"] for observation in observations}) > 1
    )
    observed_mean_interval_ns = statistics.fmean(
        observation["scheduled_interval_ns"] for observation in profile.observations
    )
    assert observed_mean_interval_ns >= 90_000
    assert observed_mean_interval_ns <= 110_000
    assert all(
        thread["stopped_state"] in {"T", "t"}
        for observation in observations
        for thread in observation["threads"]
    )
    assert all(
        "scheduler_runtime_ns" not in thread
        for observation in observations
        for thread in observation["threads"]
    )
    assert any(
        thread["stack"]
        for observation in observations
        for thread in observation["threads"]
    )
    assert all(
        frame_id in profile.frames
        for observation in observations
        for thread in observation["threads"]
        for frame_id in thread["stack"]
    )
    assert len(profile.frames) < sum(
        len(thread["stack"])
        for observation in observations
        for thread in observation["threads"]
    )
    sampled_functions = _sampled_functions(profile, observations)
    assert "_retired_worker" in sampled_functions
    assert "_deep_wait_level_two" in sampled_functions
    assert "_shallow_wait" in sampled_functions
    assert "_high_call_frequency" in sampled_functions
    assert "_low_call_frequency" in sampled_functions

    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    cumulative_by_function = {
        row.identity.function: row for row in analysis.cumulative_function_rows
    }
    assert cumulative_by_function["_retired_worker"].wall_occupancy_ns < 500_000_000
    assert (
        cumulative_by_function["_deep_wait_level_two"].wall_occupancy_ns > 600_000_000
    )
    assert cumulative_by_function["_shallow_wait"].wall_occupancy_ns > 600_000_000
    assert (
        abs(
            cumulative_by_function["_deep_wait_level_two"].wall_occupancy_ns
            - cumulative_by_function["_shallow_wait"].wall_occupancy_ns
        )
        < 50_000_000
    )
    assert (
        abs(
            cumulative_by_function["_high_call_frequency"].wall_occupancy_ns
            - cumulative_by_function["_low_call_frequency"].wall_occupancy_ns
        )
        < 100_000_000
    )

    profile_lines = profile_path.read_text(encoding="utf-8").splitlines()
    assert '"complete":false' in profile_lines[0]
    assert '"record_type":"summary"' in profile_lines[-1]
    analysis_result = subprocess.run(
        [str(_runfile("ANALYZER_BINARY")), "--profile", str(profile_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert "Profile schema: 3; complete; successful" in analysis_result.stdout
    assert "Sampling: poisson" in analysis_result.stdout
    assert "Observations:" in analysis_result.stdout
    assert "Self wall occupancy (union across threads):" in analysis_result.stdout
    assert "Cumulative wall occupancy (union across threads):" in analysis_result.stdout
    assert "Longest sampled stack paths:" in analysis_result.stdout
    assert "Longest sampled source-identified frames:" in analysis_result.stdout
    assert "_retired_worker" in analysis_result.stdout
    assert "sample hits are observations, not calls" in analysis_result.stdout


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
# PRF-019: Concurrency semantics. PRF-029: Call-frequency fixture.
# PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
# PRF-034: Parallel-CPU fixture. PRF-035: Short-function fixture.
# PRF-036: Rate convergence. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_cpu_accuracy_converges_across_rates_through_real_targets(tmp_path: Path):
    rates = (0.0005, 0.001, 0.002)
    cumulative_rows_by_rate: list[dict[str, cpu_analyzer.FunctionRow]] = []
    final_profile_path = tmp_path / "cpu-2.jsonl"
    for index, rate in enumerate(rates):
        profile_path = tmp_path / f"cpu-{index}.jsonl"
        if index == 0:
            source = _runfile("PROFILER_CPU_SOURCE")
            profile = profiler.capture(
                command=_target_command("PROFILER_CPU_SOURCE"),
                profile_path=profile_path,
                workload_path=source,
                working_directory=tmp_path,
                mean_interval_seconds=rate,
                random_seed=37,
                attachment_timeout_seconds=5,
                mode="cpu",
            )
        else:
            capture_result = subprocess.run(
                _profile_command(
                    profile_path,
                    "PROFILER_CPU_SOURCE",
                    mode="cpu",
                    mean_interval_seconds=rate,
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            assert capture_result.returncode == 0
            assert capture_result.stdout == ""
            assert capture_result.stderr == ""
            profile = schema.load(profile_path)
        assert profile.complete is True
        assert profile.success is True
        assert profile.sampling["mode"] == "cpu"
        assert profile.sampling["cpu_backend"] == "linux-schedstat"
        assert profile.sampling["python_stack_trampolines"] is False
        successful, _, _ = _assert_observations_through_exit(profile)
        assert all(
            "scheduler_runtime_ns" in thread
            for observation in successful
            for thread in observation["threads"]
        )
        analysis = analyzer.analyze(profile)
        assert isinstance(analysis, cpu_analyzer.Analysis)
        cumulative_rows = {
            row.identity.function: row for row in analysis.cumulative_function_rows
        }
        cumulative_rows_by_rate.append(cumulative_rows)
        high_call_row = cumulative_rows["_high_call_frequency"]
        low_call_row = cumulative_rows["_low_call_frequency"]
        assert (
            abs(high_call_row.cpu_time_ns - low_call_row.cpu_time_ns)
            <= high_call_row.confidence_95_ns + low_call_row.confidence_95_ns
        )
        deep_row = cumulative_rows["_deep_work_level_two"]
        shallow_row = cumulative_rows["_shallow_work"]
        assert (
            abs(deep_row.cpu_time_ns - shallow_row.cpu_time_ns)
            <= deep_row.confidence_95_ns + shallow_row.confidence_95_ns
        )
        waiting_cpu_ns = cumulative_rows["_waiting_worker"].cpu_time_ns
        assert waiting_cpu_ns < high_call_row.cpu_time_ns // 10
        assert waiting_cpu_ns < low_call_row.cpu_time_ns // 10
        assert cumulative_rows["_short_leaf"].cpu_time_ns > 250_000_000
        for function in (
            "_high_call_frequency",
            "_low_call_frequency",
            "_deep_work_level_two",
            "_shallow_work",
            "_repeated_short_leaves",
        ):
            row = cumulative_rows[function]
            assert abs(row.cpu_time_ns - 400_000_000) <= row.confidence_95_ns
        for function in ("_parallel_worker_one", "_parallel_worker_two"):
            row = cumulative_rows[function]
            assert abs(row.cpu_time_ns - 8_000_000_000) <= row.confidence_95_ns
        assert analysis.observed_cpu_ns > analysis.wall_window_ns * 3 // 2
        assert analysis.attributed_cpu_ns > 2_000_000_000
        assert analysis.unattributed_cpu_ns < 100_000_000

        if index == 0:
            # PRF-014: CPU mode. PRF-018: Focused analysis.
            selected_thread = analysis.thread_rows[0].os_thread_id
            thread_analysis = analyzer.analyze(
                profile,
                analyzer_model.AnalysisFilters(thread_ids=frozenset({selected_thread})),
            )
            assert isinstance(thread_analysis, cpu_analyzer.Analysis)
            assert thread_analysis.thread_rows[0].os_thread_id == selected_thread
            missing_function = analyzer.analyze(
                profile,
                analyzer_model.AnalysisFilters(function="not_a_function"),
            )
            assert isinstance(missing_function, cpu_analyzer.Analysis)
            assert missing_function.self_rows == []
            assert missing_function.self_function_rows == []
            assert missing_function.relationship_rows == []
            missing_file = analyzer.analyze(
                profile,
                analyzer_model.AnalysisFilters(filename="not_a_file"),
            )
            assert isinstance(missing_file, cpu_analyzer.Analysis)
            assert missing_file.self_rows == []
            assert missing_file.self_function_rows == []
            missing_caller = analyzer.analyze(
                profile,
                analyzer_model.AnalysisFilters(caller="not_a_caller"),
            )
            assert isinstance(missing_caller, cpu_analyzer.Analysis)
            assert missing_caller.relationship_rows == []
            missing_callee = analyzer.analyze(
                profile,
                analyzer_model.AnalysisFilters(callee="not_a_callee"),
            )
            assert isinstance(missing_callee, cpu_analyzer.Analysis)
            assert missing_callee.relationship_rows == []
            report_result = click.testing.CliRunner().invoke(
                analyzer.main,
                ["--profile", str(profile_path)],
            )
            assert report_result.exit_code == 0
            assert "Self CPU attribution:" in report_result.output
            assert "Failed observations" in report_result.output

    convergent_functions = (
        "_high_call_frequency",
        "_low_call_frequency",
        "_deep_work_level_two",
        "_shallow_work",
        "_repeated_short_leaves",
        "_parallel_worker_one",
        "_parallel_worker_two",
    )
    for function in convergent_functions:
        rows = [
            cumulative_rows[function] for cumulative_rows in cumulative_rows_by_rate
        ]
        assert max(row.cpu_time_ns - row.confidence_95_ns for row in rows) <= min(
            row.cpu_time_ns + row.confidence_95_ns for row in rows
        )

    analysis_result = subprocess.run(
        [str(_runfile("ANALYZER_BINARY")), "--profile", str(final_profile_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert analysis_result.stderr == ""
    assert "CPU backend: linux-schedstat" in analysis_result.stdout
    assert "Python stack trampolines: disabled" in analysis_result.stdout
    assert "Self CPU attribution:" in analysis_result.stdout
    assert "Cumulative CPU attribution:" in analysis_result.stdout
    assert "approximate 95% Poisson confidence bounds" in analysis_result.stdout
    assert "functions shorter than the sampling interval" in analysis_result.stdout


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_normal_exit_before_observation_is_an_explicit_failure(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"

    profile = profiler.capture(
        command=(sys.executable, "-c", "import time; time.sleep(0.02)"),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        mean_interval_seconds=1000,
        random_seed=7,
        attachment_timeout_seconds=5,
        mode="wall",
    )

    assert profile.complete is True
    assert profile.success is False
    assert len(profile.observations) == 1
    missed_observation = profile.observations[0]
    assert missed_observation["status"] == "missed"
    assert (
        missed_observation["failure_kind"]
        == "target-exited-before-scheduled-observation"
    )
    assert missed_observation["failure_reason"] == (
        "the target exited before the scheduled stop"
    )
    assert missed_observation["pause_duration_ns"] == 0
    assert profile.observation_counts == {
        "attempted": 0,
        "successful": 0,
        "discarded": 0,
        "missed": 1,
    }
    assert profile.failures[0]["kind"] == "target-exited-before-valid-stack"


# PRF-023: Guaranteed resume. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-027: Incremental persistence.
# PRF-041: Realistic tests.
def test_real_interrupt_preserves_observations_and_terminates_target(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    profile_process = subprocess.Popen(
        _profile_command(profile_path, "PROFILER_CONTINUOUS_SOURCE"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert _wait_for_successful_observation_records(profile_path, 2)

    profile_process.send_signal(signal.SIGTERM)
    stdout, stderr = profile_process.communicate(timeout=10)

    assert profile_process.returncode == 1
    assert stdout == b""
    assert b"Aborted!" in stderr
    profile = schema.load(profile_path)
    assert profile.complete is False
    assert profile.success is False
    assert profile.interruption_signal == signal.SIGTERM
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert profile.failures[-1]["kind"] == "profiler-interrupted"
    assert profile.observation_counts["successful"] > 1
    observations, discarded_observations = _assert_recorded_observations(
        profile.observations
    )
    assert profile.observation_counts == {
        "attempted": len(observations) + discarded_observations,
        "successful": len(observations),
        "discarded": discarded_observations,
        "missed": 0,
    }
    first_observation = observations[0]
    assert not Path(f"/proc/{first_observation['process_id']}").exists()


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_capture_records_diagnostics_and_nonzero_exit(tmp_path: Path):
    profile = _capture(
        tmp_path,
        "PROFILER_FAILURE_SOURCE",
        mean_interval_seconds=0.0001,
        mode="cpu",
    )

    assert profile.success is False
    assert profile.diagnostics_status == "present"
    assert profile.compiler_exit_status == 4
    assert profile.observation_counts["successful"] > 1
    stackless_thread_observed = False
    for observation in profile.observations:
        if observation["status"] != "successful":
            continue
        for thread in observation["threads"]:
            if not thread["stack"]:
                stackless_thread_observed = True
    assert stackless_thread_observed
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, cpu_analyzer.Analysis)
    assert analysis.unattributed_cpu_ns > 0


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-027: Incremental persistence. PRF-041: Realistic tests.
def test_main_handles_a_real_signal_in_the_calling_process(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    target = _runfile("PROFILER_CONTINUOUS_SOURCE")
    signal_sent = threading.Event()

    def interrupt_capture() -> None:
        # The deployed profiler has no helper thread that can receive this signal.
        _ = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        if _wait_for_successful_observation_records(profile_path, 2):
            os.kill(os.getpid(), signal.SIGINT)
            signal_sent.set()

    interrupt_thread = threading.Thread(target=interrupt_capture)
    interrupt_thread.start()
    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(target),
            "--working-directory",
            str(tmp_path),
            "--mean-interval-seconds",
            "0.01",
            "--",
            *_target_command("PROFILER_CONTINUOUS_SOURCE"),
        ],
    )
    interrupt_thread.join()

    assert signal_sent.is_set()
    assert result.exit_code == 1
    assert "Aborted!" in result.output
    profile = schema.load(profile_path)
    assert profile.complete is False
    assert profile.observation_counts["successful"] > 1
    assert profile.interruption_signal == signal.SIGINT
    assert profile.compiler_exit_status == -signal.SIGTERM


# PRF-023: Guaranteed resume. PRF-024: Explicit failures.
# PRF-027: Incremental persistence. PRF-041: Realistic tests.
def test_signal_during_a_stopped_observation_resumes_target(tmp_path: Path):
    profile_path = tmp_path / "stopped-interrupt.jsonl"
    target = _runfile("PROFILER_RACE_SOURCE")
    signal_sent = threading.Event()

    def interrupt_stopped_capture() -> None:
        # The deployed profiler has no helper thread that can receive this signal.
        _ = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            process_id = _observed_process_id(profile_path)
            if process_id is None:
                time.sleep(0.0001)
                continue
            try:
                status = Path(f"/proc/{process_id}/status").read_text(encoding="utf-8")
            except FileNotFoundError:
                return
            state_line = next(
                line for line in status.splitlines() if line.startswith("State:")
            )
            if state_line.split()[1] in {"T", "t"}:
                signal_sent.set()
                os.kill(os.getpid(), signal.SIGINT)
                return
            time.sleep(0.0001)

    interrupt_thread = threading.Thread(target=interrupt_stopped_capture)
    interrupt_thread.start()
    result = click.testing.CliRunner().invoke(
        profiler.main,
        [
            "--profile",
            str(profile_path),
            "--workload",
            str(target),
            "--working-directory",
            str(tmp_path),
            "--mean-interval-seconds",
            "0.0001",
            "--",
            *_target_command("PROFILER_RACE_SOURCE"),
        ],
    )
    interrupt_thread.join()

    assert signal_sent.is_set()
    assert result.exit_code == 1
    assert "Aborted!" in result.output
    profile = schema.load(profile_path)
    assert profile.complete is False
    assert profile.success is False
    assert profile.interruption_signal == signal.SIGINT
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert profile.failures[-1]["kind"] == "profiler-interrupted"
    observations, discarded_observations = _assert_recorded_observations(
        profile.observations
    )
    assert profile.observation_counts == {
        "attempted": len(observations) + discarded_observations,
        "successful": len(observations),
        "discarded": discarded_observations,
        "missed": 0,
    }
    process_id = _observed_process_id(profile_path)
    assert process_id is not None
    assert not Path(f"/proc/{process_id}").exists()


# PRF-014: CPU mode. PRF-020: Machine and human interfaces.
# PRF-022: Launcher safety. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_attachment_timeout_terminates_non_python_target(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"

    profile = profiler.capture(
        command=("/bin/sleep", "1"),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        mean_interval_seconds=0.01,
        random_seed=17,
        attachment_timeout_seconds=0.05,
        mode="cpu",
    )

    assert profile.success is False
    assert profile.python_runtime is None
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert profile.failures[0]["kind"] == "attachment-timeout"
    analysis_result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )
    assert analysis_result.exit_code == 0
    assert "Python runtime: not observed" in analysis_result.output
    assert "Capture failures (1):" in analysis_result.output
    assert "Failed observations" not in analysis_result.output


# PRF-022: Launcher safety. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
def test_non_python_target_exit_before_attachment_is_recorded(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"

    profile = profiler.capture(
        command=("/bin/sleep", "0.05"),
        profile_path=profile_path,
        workload_path=Path(__file__),
        working_directory=tmp_path,
        mean_interval_seconds=0.01,
        random_seed=19,
        attachment_timeout_seconds=1.0,
        mode="wall",
    )

    assert profile.success is False
    assert profile.python_runtime is None
    assert profile.compiler_exit_status == 0
    assert profile.failures[0]["kind"] == "target-exited-before-attachment"


# PRF-004: No stale-stack reuse. PRF-032: Real read-race fixture.
# PRF-041: Realistic tests.
def test_real_thread_race_records_a_stackless_gap(tmp_path: Path):
    observations: list[schema.Observation] = []
    for random_seed in range(5):
        profile = _capture(
            tmp_path,
            "PROFILER_RACE_SOURCE",
            mean_interval_seconds=0.0001,
            random_seed=random_seed,
        )
        observations.extend(profile.observations)
        if "discarded" in [
            observation["status"] for observation in profile.observations
        ]:
            break

    assert "discarded" in [observation["status"] for observation in observations]
    assert all(
        observation["status"] == "successful" or "threads" not in observation
        for observation in observations
    )
