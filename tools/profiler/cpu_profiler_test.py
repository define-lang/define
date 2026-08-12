import os
import subprocess
from pathlib import Path

from tools.profiler import (
    analyzer,
    analyzer_model,
    cpu_analyzer,
    cpu_profiler,
    schema,
    test_helpers,
)


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
def test_scheduler_runtime_reads_the_thread_schedstat(tmp_path: Path):
    thread_directory = tmp_path / "11"
    thread_directory.mkdir()
    _ = (thread_directory / "schedstat").write_text(
        "101 202 3\n",
        encoding="utf-8",
    )

    runtime = cpu_profiler.scheduler_runtime(thread_directory)

    assert runtime == 101


# PRF-010: Raw-data preservation. PRF-014: CPU mode.
# PRF-019: Concurrency semantics. PRF-029: Call-frequency fixture.
# PRF-030: Stack-depth fixture. PRF-033: Waiting-thread fixture.
# PRF-034: Parallel-CPU fixture. PRF-035: Short-function fixture.
# PRF-041: Realistic tests. PRF-043: Analyzer at every checkpoint.
# PRF-049: Event-driven coordination.
def test_cpu_capture_reports_scheduler_runtime_for_active_threads(tmp_path: Path):
    minimum_observations = 6_001
    profile_path = tmp_path / "cpu.jsonl"
    finish_gate = tmp_path / "finish-gate"
    os.mkfifo(finish_gate)
    event_read_file_descriptor, event_write_file_descriptor = os.pipe()
    event_reader = test_helpers.ProfilerEventReader(event_read_file_descriptor)
    capture_process = subprocess.Popen(
        test_helpers.profile_command(
            profile_path,
            "PROFILER_CPU_SOURCE",
            mode="cpu",
            mean_interval_seconds=0.001,
            event_file_descriptor=event_write_file_descriptor,
            target_arguments=(str(finish_gate),),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        pass_fds=(event_write_file_descriptor,),
    )
    os.close(event_write_file_descriptor)
    with finish_gate.open("wb", buffering=0) as finish_stream:
        workers_observed = event_reader.wait_for(
            "successful-observation-persisted",
            minimum_observations,
            timeout_seconds=240,
        )
        if workers_observed:
            _ = finish_stream.write(b"1")
        else:
            capture_process.terminate()
    capture_stdout, capture_stderr = capture_process.communicate()
    os.close(event_read_file_descriptor)

    assert workers_observed
    test_helpers.assert_capture_summary(capture_stdout, profile_path)
    assert capture_stderr == ""
    assert capture_process.returncode == 0
    profile = schema.load(profile_path)
    assert profile.complete is True
    assert profile.success is True
    assert profile.sampling["mode"] == "cpu"
    assert profile.sampling["cpu_backend"] == "linux-schedstat"
    assert profile.sampling["cpu_backend"] == "linux-schedstat"
    successful, _, _ = test_helpers.assert_observations_through_exit(profile)
    assert len(successful) >= minimum_observations
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
    active_functions = {
        "_high_call_frequency",
        "_low_call_frequency",
        "_deep_work_level_two",
        "_shallow_work",
        "_repeated_short_leaves",
        "_parallel_worker_one",
        "_parallel_worker_two",
    }
    assert active_functions <= cumulative_rows.keys()
    assert all(
        cumulative_rows[function].cpu_time_ns > 0 for function in active_functions
    )
    waiting_row = cumulative_rows.get("_waiting_worker")
    if waiting_row is not None:
        assert (
            waiting_row.cpu_time_ns
            < min(
                cumulative_rows[function].cpu_time_ns for function in active_functions
            )
            // 10
        )
    assert analysis.attributed_cpu_ns > 0

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
    assert missing_function.self_function_rows == []
    assert missing_function.self_function_rows == []
    assert missing_function.relationship_rows == []
    missing_file = analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(filename="not_a_file"),
    )
    assert isinstance(missing_file, cpu_analyzer.Analysis)
    assert missing_file.self_function_rows == []
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
    assert "CPU backend: linux-schedstat" in analysis_result.stdout
    assert "Self CPU attribution:" in analysis_result.stdout
    assert "Cumulative CPU attribution:" in analysis_result.stdout
    assert "approximate 95% Poisson confidence bounds" in analysis_result.stdout
    assert "functions shorter than the sampling interval" in analysis_result.stdout


# PRF-036: Rate convergence.
def test_cpu_confidence_bound_shrinks_with_more_observations():
    confidence_100 = cpu_analyzer._confidence_95_ns(  # pyright: ignore[reportPrivateUsage]
        500,
        1000,
        100,
    )
    confidence_400 = cpu_analyzer._confidence_95_ns(  # pyright: ignore[reportPrivateUsage]
        500,
        1000,
        400,
    )

    assert confidence_400 * 2 == confidence_100
