import collections
import dataclasses
import os
import re
import select
import signal
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import click.testing
import pytest
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

from tools.profiler import (
    analyzer,
    analyzer_model,
    cpu_analyzer,
    profiler,
    schema,
    wall_analyzer,
    wall_critical_path,
    wall_model,
)


@dataclasses.dataclass(slots=True)
class _ProfilerEventReader:
    # PRF-041: Realistic tests. PRF-049: Event-driven coordination.
    file_descriptor: int
    buffered_events: collections.deque[str] = dataclasses.field(
        default_factory=collections.deque
    )
    incomplete_event: bytes = b""

    def wait_for(
        self,
        expected_event: str,
        count: int = 1,
        *,
        timeout_seconds: float = 5,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        events_seen = 0
        while time.monotonic() < deadline:
            while self.buffered_events:
                event = self.buffered_events.popleft()
                if event == expected_event:
                    events_seen += 1
                    if events_seen == count:
                        return True
            readable, _, _ = select.select(
                [self.file_descriptor],
                [],
                [],
                deadline - time.monotonic(),
            )
            if not readable:
                return False
            event_bytes = os.read(self.file_descriptor, 4096)
            if not event_bytes:
                return False
            event_bytes = self.incomplete_event + event_bytes
            *complete_lines, self.incomplete_event = event_bytes.split(b"\n")
            self.buffered_events.extend(line.decode() for line in complete_lines)
        return False


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


def _target_command(
    source_variable: str,
    target_arguments: tuple[str, ...] = (),
) -> tuple[str, ...]:
    source = _runfile(source_variable)
    return (
        "/bin/sh",
        "-c",
        'exec "$@"',
        "profiler-test-launcher",
        sys.executable,
        str(source),
        *target_arguments,
    )


def _profile_command(
    profile_path: Path,
    source_variable: str,
    *,
    mode: schema.CaptureMode = "wall",
    mean_interval_seconds: float = 0.0001,
    event_file_descriptor: int | None = None,
    target_arguments: tuple[str, ...] = (),
) -> list[str]:
    # PRF-002: Independent sampling schedule. PRF-020: Machine and human interfaces.
    source = _runfile(source_variable)
    command = [
        str(_runfile("PROFILER_BINARY")),
        "--mode",
        mode,
        "--profile",
        str(profile_path),
        "--workload",
        str(source),
        "--mean-interval-seconds",
        str(mean_interval_seconds),
    ]
    if event_file_descriptor is not None:
        command.extend(["--event-fd", str(event_file_descriptor)])
    command.extend(["--", *_target_command(source_variable, target_arguments)])
    return command


def _assert_capture_summary(
    output: str,
    profile_path: Path,
    *,
    completeness: str = "complete",
    status: str = "successful",
):
    # PRF-020: Machine and human interfaces.
    assert output.startswith(
        f"Profile: {profile_path}\nCapture: {completeness}; {status};"
    )
    assert "\nObservations:" in output
    assert "discarded rate" in output


def _observed_process_id(profile_path: Path) -> int | None:
    try:
        profile_text = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    process_id_match = re.search(r'"process_id":(\d+)', profile_text)
    return int(process_id_match.group(1)) if process_id_match is not None else None


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
            assert isinstance(
                observation["failure_kind"],
                schema.ObservationFailureKind,
            )
            assert observation["failure_reason"]
            exception_name, separator, _ = observation["failure_reason"].partition(": ")
            assert exception_name
            assert separator
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


# PRF-020: Machine and human interfaces. PRF-025: Failure threshold.
# PRF-041: Realistic tests.
def test_main_profiles_relative_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
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
            "0.001",
            "--",
            "./target",
            "-c",
            "import time; time.sleep(2)",
        ],
    )

    assert result.exit_code == 0
    profile = schema.load(profile_path)
    assert profile.success is True
    assert profile.observation_counts["successful"] > 5
    assert profile.sampling["schedule"] == "poisson"
    assert f"Profile: {profile_path}" in result.output
    assert "Capture: complete; successful; compiler exit 0; diagnostics none" in (
        result.output
    )
    assert "discarded rate" in result.output
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    analyzer.emit_report(profile, analysis, 1)
    assert "none resolved or observed" in capsys.readouterr().out


# PRF-002: Independent sampling schedule. PRF-049: Event-driven coordination.
def test_help_hides_internal_sampling_parameters():
    result = click.testing.CliRunner().invoke(profiler.main, ["--help"])

    assert result.exit_code == 0
    assert "--mean-interval-seconds" in result.output
    assert "--event-fd" in result.output
    assert "--jitter" not in result.output
    assert "--no-jitter" not in result.output
    assert "--jitter-fraction" not in result.output
    assert "--random-seed" not in result.output


# PRF-024: Explicit failures.
def test_observation_failure_kinds_are_stable():
    observation_failure_kind = profiler._observation_failure_kind  # pyright: ignore[reportPrivateUsage]
    inconsistent_failure = profiler._InconsistentStackObservationError()  # pyright: ignore[reportPrivateUsage]
    exit_failure = profiler._TargetExitRaceError()  # pyright: ignore[reportPrivateUsage]
    resume_failure = profiler._TargetResumeError()  # pyright: ignore[reportPrivateUsage]
    stop_failure = profiler._TargetStopError()  # pyright: ignore[reportPrivateUsage]
    assert (
        observation_failure_kind(PermissionError())
        is schema.ObservationFailureKind.PERMISSION_DENIED
    )
    assert (
        observation_failure_kind(inconsistent_failure)
        is schema.ObservationFailureKind.INCONSISTENT_STACK
    )
    assert (
        observation_failure_kind(exit_failure)
        is schema.ObservationFailureKind.TARGET_EXITED_DURING_OBSERVATION
    )
    assert (
        observation_failure_kind(resume_failure)
        is schema.ObservationFailureKind.TARGET_RESUME_FAILED
    )
    assert (
        observation_failure_kind(stop_failure)
        is schema.ObservationFailureKind.TARGET_STOP_FAILED
    )
    assert (
        observation_failure_kind(RuntimeError())
        is schema.ObservationFailureKind.STACK_UNWIND_FAILED
    )
    assert (
        observation_failure_kind(ValueError())
        is schema.ObservationFailureKind.MALFORMED_OBSERVATION
    )
    assert (
        observation_failure_kind(OSError())
        is schema.ObservationFailureKind.OBSERVATION_SYSTEM_ERROR
    )


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
    _assert_capture_summary(capture_result.stdout, profile_path)
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
    assert len(observations) > 1000
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
        [
            str(_runfile("ANALYZER_BINARY")),
            "--profile",
            str(profile_path),
            "--limit",
            "25",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert (
        f"Profile schema: {schema.SCHEMA_VERSION}; complete; successful"
        in analysis_result.stdout
    )
    assert "Sampling: poisson" in analysis_result.stdout
    assert "Observations:" in analysis_result.stdout
    assert "Self wall occupancy (union across threads):" in analysis_result.stdout
    assert "Cumulative wall occupancy (union across threads):" in analysis_result.stdout
    assert "Longest sampled stack paths:" in analysis_result.stdout
    assert "Longest sampled source-identified frames:" in analysis_result.stdout
    assert "_retired_worker" in analysis_result.stdout
    assert "sample hits are observations, not calls" in analysis_result.stdout


# PRF-047: Multi-threaded critical path.
def test_uninterruptible_io_is_not_a_cross_thread_handoff():
    sample = wall_model.ThreadSample(
        identity=wall_model.ThreadIdentity(os_thread_id=1, start_time_ticks=1),
        observation_index=0,
        interval=wall_model.Interval(start_ns=0, end_ns=1),
        pre_stop_state="D",
        wait_channel="0",
        voluntary_context_switches=0,
        nonvoluntary_context_switches=0,
        stack=(1,),
    )

    assert not sample.is_handoff_waiting


# PRF-025: Failure threshold. PRF-047: Multi-threaded critical path.
# PRF-048: Critical-path fixture. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
# PRF-049: Event-driven coordination.
def test_wall_critical_path_recovers_cross_thread_handoffs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    profile_path = tmp_path / "critical-path.jsonl"
    profiler_gate = tmp_path / "profiler-gate"
    os.mkfifo(profiler_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)
    capture_process = subprocess.Popen(
        _profile_command(
            profile_path,
            "PROFILER_CRITICAL_PATH_SOURCE",
            mean_interval_seconds=0.005,
            event_file_descriptor=event_write_file_descriptor,
            target_arguments=(str(profiler_gate),),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    launcher_recorded = event_reader.wait_for("launcher-recorded")
    python_attached = event_reader.wait_for("python-attached")
    profiler_ready = event_reader.wait_for(
        "successful-observation-persisted",
        600,
        timeout_seconds=15,
    )
    if profiler_ready:
        with profiler_gate.open("wb", buffering=0) as gate_stream:
            _ = gate_stream.write(b"1")
    else:
        capture_process.terminate()
    capture_stdout, capture_stderr = capture_process.communicate()
    os.close(event_read_file_descriptor)

    assert launcher_recorded
    assert python_attached
    assert profiler_ready
    assert capture_process.returncode == 0
    _assert_capture_summary(capture_stdout, profile_path)
    assert capture_stderr == ""
    profile = schema.load(profile_path)
    assert profile.complete is True
    assert profile.success is True
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    critical_path = analysis.critical_path
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    assert python_started_ns is not None
    assert process_exited_ns is not None
    assert sum(segment.interval.duration_ns for segment in critical_path.segments) == (
        process_exited_ns - python_started_ns
    )
    required_handoffs: dict[str, wall_critical_path.ResolvedHandoff] = {}
    required_downstream_functions = (
        "_stage_two_worker",
        "_stage_three_worker",
    )
    resolved_handoffs: list[wall_critical_path.ResolvedHandoff] = []
    for handoff in critical_path.handoffs:
        if not isinstance(handoff, wall_critical_path.ResolvedHandoff):
            continue
        resolved_handoffs.append(handoff)
        assert handoff.upstream_stack
        assert handoff.downstream_stack
        downstream_functions = {
            profile.frames[frame_id]["function"]
            for frame_id in handoff.downstream_stack
        }
        for function in required_downstream_functions:
            if function in downstream_functions:
                required_handoffs[function] = handoff
    assert set(required_handoffs) == set(required_downstream_functions)
    first_handoff = required_handoffs["_stage_two_worker"]
    second_handoff = required_handoffs["_stage_three_worker"]
    terminal_thread = critical_path.terminal_thread
    assert terminal_thread is not None
    third_handoff = max(
        (
            handoff
            for handoff in resolved_handoffs
            if handoff.upstream == second_handoff.downstream
            and handoff.downstream == terminal_thread
        ),
        key=lambda handoff: handoff.target_running_ns,
    )
    assert first_handoff.downstream == second_handoff.upstream
    assert second_handoff.downstream == third_handoff.upstream
    cumulative_functions = {
        row.identity.function for row in critical_path.cumulative_function_rows
    }
    assert "_stage_one_work" in cumulative_functions
    assert "_stage_two_work" in cumulative_functions
    assert "_stage_three_work" in cumulative_functions
    assert "_final_work" in cumulative_functions
    assert "_off_path_work" not in cumulative_functions
    assert critical_path.parallel_off_path_ns > 0
    assert any(
        isinstance(segment, wall_critical_path.ResolvedSegment)
        and segment.dependent_wait is not None
        for segment in critical_path.segments
    )
    analyzer.emit_report(profile, analysis, len(critical_path.segments) + 1)
    detailed_report = capsys.readouterr().out
    assert "parallel off-path Thread" in detailed_report
    assert "dependent wait: Thread" in detailed_report
    assert "producer:" in detailed_report
    wall_critical_path.emit_report(profile, critical_path, 1)
    assert "shorter segments" in capsys.readouterr().out

    analysis_result = subprocess.run(
        [
            str(_runfile("ANALYZER_BINARY")),
            "--profile",
            str(profile_path),
            "--limit",
            "25",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert analysis_result.stderr == ""
    assert "Sampled wall critical path:" in analysis_result.stdout
    assert "Critical-path cross-thread handoffs:" in analysis_result.stdout
    assert "_stage_one_work" in analysis_result.stdout
    assert "_stage_two_work" in analysis_result.stdout
    assert "_stage_three_work" in analysis_result.stdout
    assert "_final_work" in analysis_result.stdout
    assert "parallel off-path" in analysis_result.stdout


# PRF-047: Multi-threaded critical path. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_wall_critical_path_reports_unobserved_handoff(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    profile = _capture(
        tmp_path,
        "PROFILER_UNRESOLVED_CRITICAL_PATH_SOURCE",
        mean_interval_seconds=0.2,
    )
    profile_path = tmp_path / "PROFILER_UNRESOLVED_CRITICAL_PATH_SOURCE-7.jsonl"

    assert profile.complete is True
    assert profile.success is True
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    assert len(analysis.critical_path.handoffs) == 2
    handoff, completion_handoff = analysis.critical_path.handoffs
    assert isinstance(handoff, wall_critical_path.UnresolvedHandoff)
    assert isinstance(completion_handoff, wall_critical_path.ResolvedHandoff)
    assert handoff.resolution == "unobserved"
    assert handoff.candidates == ()
    assert handoff.downstream_wait_ns > 0
    assert (
        analysis.critical_path.segments[0].interval.start_ns
        == profile.lifecycle["python_observed_target_running_ns"]
    )
    process_exited_ns = profile.lifecycle["exited_target_running_ns"]
    python_started_ns = profile.lifecycle["python_observed_target_running_ns"]
    assert process_exited_ns is not None
    assert python_started_ns is not None
    assert sum(
        segment.interval.duration_ns for segment in analysis.critical_path.segments
    ) == (process_exited_ns - python_started_ns)
    analyzer.emit_report(profile, analysis, len(analysis.critical_path.segments) + 1)
    direct_report = capsys.readouterr().out
    assert "unobserved: wake of Thread" in direct_report
    assert "candidate producers: none observed" in direct_report

    analysis_result = subprocess.run(
        [str(_runfile("ANALYZER_BINARY")), "--profile", str(profile_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert analysis_result.returncode == 0
    assert analysis_result.stderr == ""
    assert "unobserved: wake of Thread" in analysis_result.stdout
    assert "candidate producers: none observed" in analysis_result.stdout


# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-047: Multi-threaded critical path. PRF-048: Critical-path fixture.
def test_real_profile_reports_ambiguous_new_worker_handoff():
    profile = schema.load(_runfile("PROFILER_AMBIGUOUS_CRITICAL_PATH_PROFILE"))

    analysis = analyzer.analyze(profile)

    assert isinstance(analysis, wall_analyzer.Analysis)
    assert len(analysis.critical_path.handoffs) == 2
    ambiguous_handoff, completion_handoff = analysis.critical_path.handoffs
    assert isinstance(ambiguous_handoff, wall_critical_path.UnresolvedHandoff)
    assert ambiguous_handoff.resolution == "ambiguous"
    assert ambiguous_handoff.downstream_wait_ns == 0
    assert len(ambiguous_handoff.candidates) == 2
    assert isinstance(completion_handoff, wall_critical_path.ResolvedHandoff)


# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-047: Multi-threaded critical path. PRF-048: Critical-path fixture.
def test_real_profile_reports_worker_waiting_from_first_observation():
    profile = schema.load(_runfile("PROFILER_INITIAL_WAIT_CRITICAL_PATH_PROFILE"))

    analysis = analyzer.analyze(profile)

    assert isinstance(analysis, wall_analyzer.Analysis)
    assert len(analysis.critical_path.handoffs) == 2
    initial_handoff, completion_handoff = analysis.critical_path.handoffs
    assert isinstance(initial_handoff, wall_critical_path.ResolvedHandoff)
    assert initial_handoff.downstream_wait_ns > 0
    assert isinstance(completion_handoff, wall_critical_path.ResolvedHandoff)


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
# PRF-019: Concurrency semantics. PRF-029: Call-frequency fixture.
# PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
# PRF-034: Parallel-CPU fixture. PRF-035: Short-function fixture.
# PRF-036: Rate convergence. PRF-041: Realistic tests.
# PRF-043: Analyzer at every checkpoint.
def test_cpu_accuracy_converges_across_rates_through_real_targets(tmp_path: Path):
    rates = (0.00025, 0.0005, 0.001)
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
            _assert_capture_summary(capture_result.stdout, profile_path)
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
    exit_gate = tmp_path / "exit-gate"
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        _profile_command(
            profile_path,
            "PROFILER_EXIT_SOURCE",
            mean_interval_seconds=1000,
            event_file_descriptor=event_write_file_descriptor,
            target_arguments=(str(exit_gate),),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    python_attached = event_reader.wait_for("python-attached")
    with exit_gate.open("wb") as exit_gate_writer:
        _ = exit_gate_writer.write(b"\0")
    capture_stdout, capture_stderr = profile_process.communicate()
    os.close(event_read_file_descriptor)

    assert python_attached
    assert profile_process.returncode == 1
    _assert_capture_summary(capture_stdout, profile_path, status="unsuccessful")
    assert capture_stderr == "Error: profile capture was not successful\n"
    profile = schema.load(profile_path)

    assert profile.complete is True
    assert profile.success is False
    assert len(profile.observations) == 1
    missed_observation = profile.observations[0]
    assert missed_observation["status"] == "missed"
    assert (
        missed_observation["failure_kind"]
        == schema.ObservationFailureKind.TARGET_EXITED_BEFORE_SCHEDULED_OBSERVATION
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
    assert (
        profile.failures[0]["kind"]
        == schema.CaptureFailureKind.TARGET_EXITED_BEFORE_VALID_STACK
    )


# PRF-023: Guaranteed resume. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-041: Realistic tests.
# PRF-049: Event-driven coordination.
def test_event_reader_failure_terminates_target_and_is_recorded(tmp_path: Path):
    profile_path = tmp_path / "event-reader-failure.jsonl"
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        _profile_command(
            profile_path,
            "PROFILER_CONTINUOUS_SOURCE",
            mean_interval_seconds=0.1,
            event_file_descriptor=event_write_file_descriptor,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    launcher_recorded = event_reader.wait_for("launcher-recorded")
    python_attached = event_reader.wait_for("python-attached")
    os.close(event_read_file_descriptor)

    capture_stdout, capture_stderr = profile_process.communicate()

    assert launcher_recorded
    assert python_attached
    assert profile_process.returncode == 1
    _assert_capture_summary(
        capture_stdout,
        profile_path,
        status="unsuccessful",
    )
    assert capture_stderr == "Error: profile capture was not successful\n"
    profile = schema.load(profile_path)
    assert profile.complete is True
    assert profile.success is False
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert len(profile.failures) == 1
    assert (
        profile.failures[0]["kind"]
        == schema.CaptureFailureKind.PROFILER_EVENT_WRITE_FAILED
    )


# PRF-023: Guaranteed resume. PRF-024: Explicit failures.
# PRF-026: No silent partial success. PRF-027: Incremental persistence.
# PRF-041: Realistic tests. PRF-049: Event-driven coordination.
def test_real_interrupt_preserves_observations_and_terminates_target(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        _profile_command(
            profile_path,
            "PROFILER_CONTINUOUS_SOURCE",
            event_file_descriptor=event_write_file_descriptor,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    observations_persisted = event_reader.wait_for(
        "successful-observation-persisted",
        2,
    )

    profile_process.send_signal(signal.SIGTERM)
    stdout, stderr = profile_process.communicate()
    os.close(event_read_file_descriptor)

    assert observations_persisted
    assert profile_process.returncode == 1
    _assert_capture_summary(
        stdout.decode(),
        profile_path,
        completeness="incomplete",
        status="unsuccessful",
    )
    assert b"Aborted!" in stderr
    profile = schema.load(profile_path)
    assert profile.complete is False
    assert profile.success is False
    assert profile.interruption_signal == signal.SIGTERM
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert (
        profile.failures[-1]["kind"] == schema.CaptureFailureKind.PROFILER_INTERRUPTED
    )
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
# PRF-049: Event-driven coordination.
def test_main_handles_a_real_signal_in_the_calling_process(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    target = _runfile("PROFILER_CONTINUOUS_SOURCE")
    signal_sent = threading.Event()
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)

    def interrupt_capture() -> None:
        # The deployed profiler has no helper thread that can receive this signal.
        _ = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        if event_reader.wait_for(
            "successful-observation-persisted",
            2,
        ):
            os.kill(os.getpid(), signal.SIGINT)
            signal_sent.set()

    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    interrupt_thread = threading.Thread(target=interrupt_capture)
    interrupt_thread.start()
    try:
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
                "--event-fd",
                str(event_write_file_descriptor),
                "--",
                *_target_command("PROFILER_CONTINUOUS_SOURCE"),
            ],
        )
    finally:
        _ = signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        os.close(event_write_file_descriptor)
    interrupt_thread.join()
    os.close(event_read_file_descriptor)

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
# PRF-049: Event-driven coordination.
def test_signal_during_a_stopped_observation_resumes_target(tmp_path: Path):
    profile_path = tmp_path / "stopped-interrupt.jsonl"
    target = _runfile("PROFILER_RACE_SOURCE")
    signal_sent = threading.Event()
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = _ProfilerEventReader(event_read_file_descriptor)

    def interrupt_stopped_capture() -> None:
        # The deployed profiler has no helper thread that can receive this signal.
        _ = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        observed = event_reader.wait_for("successful-observation-persisted")
        if observed and event_reader.wait_for("target-stopped"):
            signal_sent.set()
            os.kill(os.getpid(), signal.SIGINT)

    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
    interrupt_thread = threading.Thread(target=interrupt_stopped_capture)
    interrupt_thread.start()
    try:
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
                "--event-fd",
                str(event_write_file_descriptor),
                "--",
                *_target_command("PROFILER_RACE_SOURCE"),
            ],
        )
    finally:
        _ = signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        os.close(event_write_file_descriptor)
    interrupt_thread.join()
    os.close(event_read_file_descriptor)

    assert signal_sent.is_set()
    assert result.exit_code == 1
    assert "Aborted!" in result.output
    profile = schema.load(profile_path)
    assert profile.complete is False
    assert profile.success is False
    assert profile.interruption_signal == signal.SIGINT
    assert profile.compiler_exit_status == -signal.SIGTERM
    assert (
        profile.failures[-1]["kind"] == schema.CaptureFailureKind.PROFILER_INTERRUPTED
    )
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
    assert profile.failures[0]["kind"] == schema.CaptureFailureKind.ATTACHMENT_TIMEOUT
    analysis_result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )
    assert analysis_result.exit_code == 0
    assert "Python runtime: not observed" in analysis_result.output
    assert "Capture failures (1):" in analysis_result.output
    assert "Unretained observations" not in analysis_result.output


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
    assert (
        profile.failures[0]["kind"]
        == schema.CaptureFailureKind.TARGET_EXITED_BEFORE_ATTACHMENT
    )


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
