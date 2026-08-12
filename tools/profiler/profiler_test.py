import os
import re
import signal
import subprocess
import sys
import threading
from pathlib import Path

import click.testing
import pytest

from tools.profiler import (
    analyzer,
    profiler,
    schema,
    test_helpers,
    wall_analyzer,
    wall_critical_path,
    wall_model,
)


def _observed_process_id(profile_path: Path) -> int | None:
    try:
        profile_text = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    process_id_match = re.search(r'"process_id":(\d+)', profile_text)
    return int(process_id_match.group(1)) if process_id_match is not None else None


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
    exit_gate = tmp_path / "exit-gate"
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    release_succeeded = threading.Event()

    def release_target() -> None:
        if event_reader.wait_for(
            "successful-observation-persisted",
            1_001,
            timeout_seconds=30,
        ):
            with exit_gate.open("wb") as exit_gate_writer:
                _ = exit_gate_writer.write(b"1")
            release_succeeded.set()

    release_thread = threading.Thread(target=release_target)
    release_thread.start()
    profile_process = subprocess.Popen(
        [
            str(test_helpers.runfile("PROFILER_BINARY")),
            "--profile",
            str(profile_path),
            "--workload",
            str(Path(__file__)),
            "--working-directory",
            str(tmp_path),
            "--mean-interval-seconds",
            "0.001",
            "--event-fd",
            str(event_write_file_descriptor),
            "--",
            "./target",
            "-c",
            "import pathlib, sys; pathlib.Path(sys.argv[1]).read_bytes()",
            str(exit_gate),
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    profile_stdout, profile_stderr = profile_process.communicate()
    release_thread.join()
    os.close(event_read_file_descriptor)

    assert release_succeeded.is_set()
    assert profile_process.returncode == 0
    assert profile_stderr == ""
    profile = schema.load(profile_path)
    assert profile.success is True
    assert profile.observation_counts["successful"] > 1_000
    assert profile.sampling["schedule"] == "poisson"
    assert f"Profile: {profile_path}" in profile_stdout
    assert "Capture: complete; successful; compiler exit 0; diagnostics none" in (
        profile_stdout
    )
    assert "discarded rate" in profile_stdout
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    analyzer.emit_report(profile, analysis, 1)
    report = capsys.readouterr().out
    if profile.observation_counts["missed"]:
        final_observation = profile.observations[-1]
        assert final_observation["status"] == "missed"
        assert final_observation["failure_kind"].value in report
    else:
        assert "none resolved or observed" in report


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


# PRF-004: No stale-stack reuse. PRF-032: Read-race handling.
def test_discarded_observation_does_not_retain_threads():
    target = subprocess.Popen(
        ("/bin/cat",),
        stdin=subprocess.PIPE,
        text=True,
    )
    try:
        capture = profiler._failed_observation_capture(  # pyright: ignore[reportPrivateUsage]
            target,
            profiler._InconsistentStackObservationError(  # pyright: ignore[reportPrivateUsage]
                "thread identity changed"
            ),
            observation_index=3,
            scheduled_interval_ns=10,
            launched_ns=20,
            total_pause_ns=0,
            pause_started_ns=30,
            pause_ended_ns=40,
            failure_kind=schema.ObservationFailureKind.INCONSISTENT_STACK,
        )
    finally:
        target.terminate()
        _ = target.wait()

    assert isinstance(
        capture.result,
        profiler._FailedObservationResult,  # pyright: ignore[reportPrivateUsage]
    )
    assert capture.result.status == "discarded"
    assert not hasattr(capture.result, "threads")


# PRF-002: Independent sampling schedule. PRF-003: Pause exclusion.
# PRF-005: Lifecycle-bounded attribution. PRF-006: Complete-process stop.
# PRF-007: Consistent stack. PRF-011: Complete invocation.
# PRF-013: Wall mode. PRF-015: Full stacks. PRF-016: Source identity.
# PRF-020: Machine and human interfaces. PRF-021: Version match.
# PRF-022: Launcher safety. PRF-025: Failure threshold.
# PRF-027: Incremental persistence. PRF-028: Bounded storage.
# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
def test_public_binaries_capture_and_analyze_target(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    launcher_gate = tmp_path / "launcher-gate"
    exit_gate = tmp_path / "exit-gate"
    os.mkfifo(launcher_gate)
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    capture_process = subprocess.Popen(
        test_helpers.profile_command(
            profile_path,
            "PROFILER_EXIT_SOURCE",
            mean_interval_seconds=0.01,
            event_file_descriptor=event_write_file_descriptor,
            launcher_gate=launcher_gate,
            target_arguments=(str(exit_gate),),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    launcher_recorded = event_reader.wait_for(
        "launcher-recorded",
        timeout_seconds=10,
    )
    if launcher_recorded:
        with launcher_gate.open("wb", buffering=0) as launcher_gate_stream:
            _ = launcher_gate_stream.write(b"1\n")
        with exit_gate.open("wb", buffering=0) as exit_gate_stream:
            target_observed = event_reader.wait_for(
                "successful-observation-persisted",
                10,
            )
            if target_observed:
                _ = exit_gate_stream.write(b"1")
            else:
                capture_process.terminate()
    else:
        target_observed = False
        capture_process.terminate()
    capture_stdout, capture_stderr = capture_process.communicate()
    os.close(event_read_file_descriptor)

    assert launcher_recorded
    assert target_observed
    test_helpers.assert_capture_summary(capture_stdout, profile_path)
    assert capture_stderr == ""
    assert capture_process.returncode == 0
    profile = schema.load(profile_path)
    assert profile.complete is True
    assert profile.success is True
    assert profile.sampling["schedule"] == "poisson"
    assert isinstance(profile.sampling["random_seed"], int)
    assert profile.python_runtime is not None
    assert (
        profile.launcher_executable["device"],
        profile.launcher_executable["inode"],
    ) != (
        profile.python_runtime["executable"]["device"],
        profile.python_runtime["executable"]["inode"],
    )
    profiler_executable = Path("/proc/self/exe").stat()
    assert (
        profile.python_runtime["executable"]["device"],
        profile.python_runtime["executable"]["inode"],
    ) == (profiler_executable.st_dev, profiler_executable.st_ino)
    observations, discarded, missed = test_helpers.assert_observations_through_exit(
        profile
    )
    assert len(observations) >= 10
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
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)

    profile_lines = profile_path.read_text(encoding="utf-8").splitlines()
    assert '"complete":false' in profile_lines[0]
    assert '"record_type":"summary"' in profile_lines[-1]
    analysis_result = subprocess.run(
        [
            str(test_helpers.runfile("ANALYZER_BINARY")),
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
    assert "sample hits are observations, not calls" in analysis_result.stdout


# PRF-029: Call-frequency fixture. PRF-030: Stack-depth fixture.
# PRF-031: Retired-thread fixture. PRF-033: Waiting-thread fixture.
# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
def test_continuous_profile_reports_thread_lifecycles():
    profile = schema.load(test_helpers.runfile("PROFILER_CONTINUOUS_PROFILE"))
    observations, _, _ = test_helpers.assert_observations_through_exit(profile)
    sampled_functions = _sampled_functions(profile, observations)
    assert {
        "_retired_worker",
        "_deep_wait_level_two",
        "_shallow_wait",
        "_high_call_frequency",
        "_low_call_frequency",
    } <= sampled_functions

    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    cumulative_by_function = {
        row.identity.function: row for row in analysis.cumulative_function_rows
    }
    assert (
        cumulative_by_function["_retired_worker"].wall_occupancy_ns
        < cumulative_by_function["_deep_wait_level_two"].wall_occupancy_ns
    )
    assert (
        cumulative_by_function["_retired_worker"].wall_occupancy_ns
        < cumulative_by_function["_shallow_wait"].wall_occupancy_ns
    )


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


# PRF-047: Multi-threaded critical path. PRF-048: Critical-path fixture.
# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
def test_wall_critical_path_recovers_cross_thread_handoffs(
    capsys: pytest.CaptureFixture[str],
):
    profile_path = test_helpers.runfile("PROFILER_CRITICAL_PATH_PROFILE")
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
            str(test_helpers.runfile("ANALYZER_BINARY")),
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
    capsys: pytest.CaptureFixture[str],
):
    profile_path = test_helpers.runfile("PROFILER_UNRESOLVED_CRITICAL_PATH_PROFILE")
    profile = schema.load(profile_path)

    assert profile.complete is True
    assert profile.success is True
    analysis = analyzer.analyze(profile)
    assert isinstance(analysis, wall_analyzer.Analysis)
    assert len(analysis.critical_path.handoffs) == 1
    handoff = analysis.critical_path.handoffs[0]
    assert isinstance(handoff, wall_critical_path.UnresolvedHandoff)
    assert handoff.resolution == "unobserved"
    assert handoff.candidates == ()
    assert handoff.downstream_wait_ns > 0
    assert analysis.critical_path.wait_ns == handoff.downstream_wait_ns
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
        [
            str(test_helpers.runfile("ANALYZER_BINARY")),
            "--profile",
            str(profile_path),
        ],
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
    profile = schema.load(
        test_helpers.runfile("PROFILER_AMBIGUOUS_CRITICAL_PATH_PROFILE")
    )

    analysis = analyzer.analyze(profile)

    assert isinstance(analysis, wall_analyzer.Analysis)
    ambiguous_handoffs = [
        handoff
        for handoff in analysis.critical_path.handoffs
        if isinstance(handoff, wall_critical_path.UnresolvedHandoff)
    ]
    assert len(ambiguous_handoffs) == 1
    ambiguous_handoff = ambiguous_handoffs[0]
    assert isinstance(ambiguous_handoff, wall_critical_path.UnresolvedHandoff)
    assert ambiguous_handoff.resolution == "ambiguous"
    assert ambiguous_handoff.downstream_wait_ns == 0
    assert len(ambiguous_handoff.candidates) == 2
    assert isinstance(
        analysis.critical_path.handoffs[-1],
        wall_critical_path.ResolvedHandoff,
    )
    process_id = profile.observations[0]["process_id"]
    first_resolved_segment = next(
        segment
        for segment in analysis.critical_path.segments
        if isinstance(segment, wall_critical_path.ResolvedSegment)
    )
    assert first_resolved_segment.identity.os_thread_id == process_id


# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-047: Multi-threaded critical path. PRF-048: Critical-path fixture.
def test_real_profile_reports_worker_waiting_from_first_observation():
    profile = schema.load(
        test_helpers.runfile("PROFILER_INITIAL_WAIT_CRITICAL_PATH_PROFILE")
    )

    analysis = analyzer.analyze(profile)

    assert isinstance(analysis, wall_analyzer.Analysis)
    assert len(analysis.critical_path.handoffs) == 2
    initial_handoff, completion_handoff = analysis.critical_path.handoffs
    assert isinstance(initial_handoff, wall_critical_path.ResolvedHandoff)
    assert initial_handoff.downstream_wait_ns > 0
    assert isinstance(completion_handoff, wall_critical_path.ResolvedHandoff)


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-041: Realistic tests.
def test_normal_exit_before_observation_is_an_explicit_failure(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    exit_gate = tmp_path / "exit-gate"
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        test_helpers.profile_command(
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
    test_helpers.assert_capture_summary(
        capture_stdout, profile_path, status="unsuccessful"
    )
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
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        test_helpers.profile_command(
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
    test_helpers.assert_capture_summary(
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
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    profile_process = subprocess.Popen(
        test_helpers.profile_command(
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
    test_helpers.assert_capture_summary(
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
    observations, discarded_observations = test_helpers.assert_recorded_observations(
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
    profile_path = tmp_path / "failure.jsonl"
    exit_gate = tmp_path / "failure-exit-gate"
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    capture_process = subprocess.Popen(
        test_helpers.profile_command(
            profile_path,
            "PROFILER_FAILURE_SOURCE",
            mode="cpu",
            mean_interval_seconds=0.001,
            event_file_descriptor=event_write_file_descriptor,
            target_arguments=(str(exit_gate),),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    with exit_gate.open("wb", buffering=0) as exit_stream:
        observations_persisted = event_reader.wait_for(
            "successful-observation-persisted",
            2,
        )
        if observations_persisted:
            _ = exit_stream.write(b"1")
        else:
            capture_process.terminate()
    capture_stdout, capture_stderr = capture_process.communicate()
    os.close(event_read_file_descriptor)

    assert observations_persisted
    assert capture_process.returncode == 1
    test_helpers.assert_capture_summary(
        capture_stdout, profile_path, status="unsuccessful"
    )
    assert capture_stderr == (
        "target diagnostic\nError: profile capture was not successful\n"
    )
    profile = schema.load(profile_path)
    assert profile.success is False
    assert profile.diagnostics_status == "present"
    assert profile.compiler_exit_status == 4
    assert profile.observation_counts["successful"] > 1


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-027: Incremental persistence. PRF-041: Realistic tests.
# PRF-049: Event-driven coordination.
def test_main_handles_a_real_signal_in_the_calling_process(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    target = test_helpers.runfile("PROFILER_CONTINUOUS_SOURCE")
    signal_sent = threading.Event()
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)

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
                *test_helpers.target_command("PROFILER_CONTINUOUS_SOURCE"),
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
    target = test_helpers.runfile("PROFILER_INTERRUPT_SOURCE")
    signal_sent = threading.Event()
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)

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
                *test_helpers.target_command("PROFILER_INTERRUPT_SOURCE"),
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
    observations, discarded_observations = test_helpers.assert_recorded_observations(
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
    target_gate = tmp_path / "target-gate"
    os.mkfifo(target_gate)

    profile = profiler.capture(
        command=("/bin/cat", str(target_gate)),
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
# PRF-049: Event-driven coordination.
def test_non_python_target_exit_before_attachment_is_recorded(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    exit_gate = tmp_path / "exit-gate"
    os.mkfifo(exit_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    target_released = threading.Event()

    def release_target():
        # SIGCHLD must remain available to the profiler's event wait.
        _ = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGCHLD})
        if event_reader.wait_for("launcher-recorded"):
            with exit_gate.open("wb"):
                pass
            target_released.set()

    release_thread = threading.Thread(target=release_target)
    release_thread.start()
    try:
        profile = profiler.capture(
            command=("/bin/cat", str(exit_gate)),
            profile_path=profile_path,
            workload_path=Path(__file__),
            working_directory=tmp_path,
            mean_interval_seconds=0.01,
            random_seed=19,
            attachment_timeout_seconds=1.0,
            mode="wall",
            event_file_descriptor=event_write_file_descriptor,
        )
    finally:
        os.close(event_write_file_descriptor)
    release_thread.join()
    os.close(event_read_file_descriptor)

    assert target_released.is_set()
    assert profile.success is False
    assert profile.python_runtime is None
    assert profile.compiler_exit_status == 0
    assert (
        profile.failures[0]["kind"]
        == schema.CaptureFailureKind.TARGET_EXITED_BEFORE_ATTACHMENT
    )
