import json
from pathlib import Path

import click.testing
import pytest

from tools.profiler import analyzer, analyzer_model, schema, wall_analyzer


# PRF-016: Source identity. PRF-020: Machine and human interfaces.
@pytest.mark.parametrize(
    ("filename", "display"),
    [
        (
            "/workspace/runfiles/_main/define/compiler/driver.py",
            "define/compiler/driver.py",
        ),
        ("/venv/site-packages/click/core.py", "site-packages/click/core.py"),
        ("/runtime/lib/python3.14/pathlib.py", "lib/python3.14/pathlib.py"),
        ("<string>", "<string>"),
    ],
)
def test_displays_source_identity_without_environment_prefix(
    filename: str,
    display: str,
):
    assert analyzer_model.display_filename(filename) == display


# PRF-016: Source identity. PRF-020: Machine and human interfaces.
def test_displays_only_the_filename_within_an_ordered_stack():
    assert (
        analyzer_model.display_stack_filename("/repo/define/compiler/driver.py")
        == "driver.py"
    )


def _analyze_wall(
    profile: schema.RawProfile,
    filters: analyzer_model.AnalysisFilters = analyzer_model.DEFAULT_FILTERS,
) -> wall_analyzer.Analysis:
    # PRF-013: Wall mode.
    analysis = analyzer.analyze(profile, filters)
    assert isinstance(analysis, wall_analyzer.Analysis)
    return analysis


def _controlled_profile() -> schema.RawProfile:
    # PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
    # Exact attribution boundaries and invalid capture states require fixed values.
    frames: dict[int, schema.Frame] = {
        0: {
            "frame_id": 0,
            "filename": "/repo/define/compiler/driver.py",
            "function": "compile_source",
            "line": 10,
        },
        1: {
            "frame_id": 1,
            "filename": "/repo/define/compiler/codegen.py",
            "function": "generate_code",
            "line": 20,
        },
        2: {
            "frame_id": 2,
            "filename": "/repo/define/compiler/validator.py",
            "function": "validate_graph",
            "line": 30,
        },
        3: {
            "frame_id": 3,
            "filename": "/repo/define/compiler/codegen.py",
            "function": "generate_code",
            "line": 21,
        },
    }
    first_observation: schema.SuccessfulObservation = {
        "observation_index": 0,
        "scheduled_interval_ns": 20,
        "host_monotonic_ns": 120,
        "target_running_ns": 20,
        "pause_started_ns": 120,
        "pause_ended_ns": 125,
        "pause_duration_ns": 5,
        "process_id": 42,
        "status": "successful",
        "threads": [
            {
                "os_thread_id": 42,
                "start_time_ticks": 100,
                "pre_stop_state": "R",
                "wait_channel": "0",
                "voluntary_context_switches": 3,
                "nonvoluntary_context_switches": 1,
                "stopped_state": "T",
                "stack": [0, 3],
            },
            {
                "os_thread_id": 43,
                "start_time_ticks": 101,
                "pre_stop_state": "S",
                "wait_channel": "futex_wait_queue",
                "voluntary_context_switches": 5,
                "nonvoluntary_context_switches": 0,
                "stopped_state": "T",
                "stack": [0, 2],
            },
        ],
    }
    failed_observation: schema.FailedObservation = {
        "observation_index": 1,
        "scheduled_interval_ns": 30,
        "host_monotonic_ns": 155,
        "target_running_ns": 50,
        "pause_started_ns": 155,
        "pause_ended_ns": 160,
        "pause_duration_ns": 5,
        "process_id": 42,
        "status": "discarded",
        "failure_kind": "RuntimeError",
        "failure_reason": "remote stack changed",
    }
    final_observation: schema.SuccessfulObservation = {
        "observation_index": 2,
        "scheduled_interval_ns": 30,
        "host_monotonic_ns": 190,
        "target_running_ns": 80,
        "pause_started_ns": 190,
        "pause_ended_ns": 195,
        "pause_duration_ns": 5,
        "process_id": 42,
        "status": "successful",
        "threads": [
            {
                "os_thread_id": 42,
                "start_time_ticks": 100,
                "pre_stop_state": "R",
                "wait_channel": "0",
                "voluntary_context_switches": 4,
                "nonvoluntary_context_switches": 1,
                "stopped_state": "T",
                "stack": [0, 1],
            }
        ],
    }
    return schema.RawProfile(
        schema_version=3,
        complete=True,
        success=True,
        command=["/repo/compiler", "compile"],
        working_directory="/repo",
        workload_path="/repo/source.dfn",
        workload_sha256="abc123",
        sampling={
            "mode": "wall",
            "schedule": "poisson",
            "mean_interval_seconds": 0.03,
            "random_seed": 7,
            "attachment_timeout_seconds": 10.0,
        },
        sampling_statistics={
            "interval_count": 2,
            "minimum_interval_ns": 30,
            "mean_interval_ns": 30,
            "maximum_interval_ns": 30,
            "total_pause_ns": 15,
            "discarded_rate": 1 / 3,
        },
        launcher_executable={
            "path": "/usr/bin/bash",
            "device": 1,
            "inode": 2,
        },
        python_runtime={
            "version": "3.14.4",
            "minor_version": "3.14",
            "free_threaded": True,
            "executable": {
                "path": "/usr/bin/python3.14t",
                "device": 1,
                "inode": 3,
            },
        },
        lifecycle={
            "launched_ns": 100,
            "python_observed_ns": 100,
            "python_observed_target_running_ns": 0,
            "exited_ns": 215,
            "exited_target_running_ns": 100,
        },
        frames=frames,
        observations=[
            first_observation,
            failed_observation,
            final_observation,
        ],
        failures=[],
        thread_lifecycles=[
            {
                "os_thread_id": 42,
                "start_time_ticks": 100,
                "first_observation_index": 0,
                "first_target_running_ns": 20,
                "last_observation_index": 2,
                "last_target_running_ns": 80,
            },
            {
                "os_thread_id": 43,
                "start_time_ticks": 101,
                "first_observation_index": 0,
                "first_target_running_ns": 20,
                "last_observation_index": 0,
                "last_target_running_ns": 20,
            },
        ],
        observation_counts={
            "attempted": 3,
            "successful": 2,
            "discarded": 1,
            "missed": 0,
        },
        compiler_exit_status=0,
        diagnostics_status="none",
        interruption_signal=None,
    )


def _wire_records(profile: schema.RawProfile) -> list[schema.ProfileRecord]:
    # Incomplete and invalid wire states cannot come from a successful real capture.
    records: list[schema.ProfileRecord] = [
        {
            "record_type": "header",
            "schema_version": profile.schema_version,
            "complete": False,
            "command": profile.command,
            "working_directory": profile.working_directory,
            "workload_path": profile.workload_path,
            "workload_sha256": profile.workload_sha256,
            "sampling": profile.sampling,
            "launcher_executable": profile.launcher_executable,
            "launched_ns": profile.lifecycle["launched_ns"],
        }
    ]
    runtime = profile.python_runtime
    python_observed_ns = profile.lifecycle["python_observed_ns"]
    python_observed_target_running_ns = profile.lifecycle[
        "python_observed_target_running_ns"
    ]
    if (
        runtime is not None
        and python_observed_ns is not None
        and python_observed_target_running_ns is not None
    ):
        records.append(
            {
                "record_type": "runtime",
                "python_runtime": runtime,
                "python_observed_ns": python_observed_ns,
                "python_observed_target_running_ns": (
                    python_observed_target_running_ns
                ),
            }
        )
    records.extend(
        {"record_type": "frame", "frame": frame} for frame in profile.frames.values()
    )
    records.extend(
        {"record_type": "observation", "observation": observation}
        for observation in profile.observations
    )
    records.extend(
        {"record_type": "failure", "failure": failure} for failure in profile.failures
    )
    statistics = profile.sampling_statistics
    compiler_exit_status = profile.compiler_exit_status
    if statistics is not None and compiler_exit_status is not None:
        records.append(
            {
                "record_type": "summary",
                "complete": profile.complete,
                "success": profile.success,
                "lifecycle": profile.lifecycle,
                "thread_lifecycles": profile.thread_lifecycles,
                "sampling_statistics": statistics,
                "observation_counts": profile.observation_counts,
                "compiler_exit_status": compiler_exit_status,
                "diagnostics_status": (
                    "present" if profile.diagnostics_status == "present" else "none"
                ),
                "interruption_signal": profile.interruption_signal,
            }
        )
    return records


def _write_records(profile_path: Path, records: list[schema.ProfileRecord]) -> None:
    _ = profile_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


# PRF-004: No stale-stack reuse. PRF-005: Lifecycle-bounded attribution.
# PRF-015: Full stacks. PRF-019: Concurrency semantics.
def test_analysis_preserves_failure_gap_and_retired_thread_boundary():
    analysis = _analyze_wall(_controlled_profile())

    assert analysis.wall_window_ns == 100
    assert analysis.attributed_wall_ns == 55
    assert analysis.unattributed_wall_ns == 45
    assert [row.identity.function for row in analysis.self_function_rows] == [
        "generate_code",
        "validate_graph",
    ]
    assert analysis.self_function_rows[0].wall_occupancy_ns == 55
    assert analysis.self_function_rows[1].wall_occupancy_ns == 25
    cumulative_by_function = {
        row.identity.function: row for row in analysis.cumulative_function_rows
    }
    assert set(cumulative_by_function) == {
        "compile_source",
        "generate_code",
        "validate_graph",
    }
    assert cumulative_by_function["compile_source"].wall_occupancy_ns == 55
    assert cumulative_by_function["compile_source"].thread_time_ns == 80
    assert [(row.os_thread_id, row.occupancy_ns) for row in analysis.thread_rows] == [
        (42, 55),
        (43, 25),
    ]
    assert [
        [identity.function for identity in row.stack_path]
        for row in analysis.stack_path_rows
    ] == [
        ["compile_source", "generate_code"],
        ["compile_source", "validate_graph"],
    ]
    assert analysis.stack_path_rows[0].longest_span_ns == 30


# PRF-010: Raw-data preservation. PRF-019: Concurrency semantics.
def test_analysis_reports_observed_time_without_a_python_stack_as_unattributed():
    profile = _controlled_profile()
    final_observation = profile.observations[2]
    assert final_observation["status"] == "successful"
    final_observation["threads"][0]["stack"] = []

    analysis = _analyze_wall(profile)

    assert analysis.attributed_wall_ns == 25
    assert analysis.unattributed_wall_ns == 75
    assert [
        (
            row.os_thread_id,
            row.occupancy_ns,
            row.attributed_occupancy_ns,
        )
        for row in analysis.thread_rows
    ] == [
        (42, 55, 25),
        (43, 25, 25),
    ]


# PRF-010: Raw-data preservation. PRF-024: Explicit failures.
# PRF-027: Incremental persistence.
def test_analysis_and_report_handle_partial_capture_before_attachment(tmp_path: Path):
    profile = _controlled_profile()
    profile.success = False
    profile.complete = False
    profile.python_runtime = None
    profile.lifecycle["python_observed_ns"] = None
    profile.lifecycle["python_observed_target_running_ns"] = None
    profile.lifecycle["exited_ns"] = None
    profile.lifecycle["exited_target_running_ns"] = None
    profile.observations = []
    profile.failures = [
        {
            "host_monotonic_ns": 110,
            "target_running_ns": None,
            "kind": "attachment-timeout",
            "reason": "target remained a launcher",
        }
    ]
    profile.sampling_statistics = None
    profile.thread_lifecycles = []
    profile.observation_counts = {
        "attempted": 0,
        "successful": 0,
        "discarded": 0,
        "missed": 0,
    }
    profile.compiler_exit_status = None
    profile.diagnostics_status = "unknown"
    profile_path = tmp_path / "partial.jsonl"
    _write_records(profile_path, _wire_records(profile))

    analysis = _analyze_wall(profile)
    result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )

    assert analysis.self_rows == []
    assert analysis.cumulative_rows == []
    assert analysis.relationship_rows == []
    assert analysis.thread_rows == []
    assert analysis.wall_window_ns == 0
    assert analysis.attributed_wall_ns == 0
    assert analysis.unattributed_wall_ns == 0
    assert result.exit_code == 0
    assert "Python runtime: not observed" in result.output
    assert "Threads observed: 0" in result.output
    assert "Capture failures (1):" in result.output
    assert "attachment-timeout: target remained a launcher" in result.output
    assert "Unretained observations" not in result.output


# PRF-011: Complete invocation. PRF-022: Launcher safety.
def test_analysis_does_not_attribute_observations_before_python_attachment():
    profile = _controlled_profile()
    profile.python_runtime = None
    profile.lifecycle["python_observed_ns"] = None
    profile.lifecycle["python_observed_target_running_ns"] = None

    analysis = _analyze_wall(profile)

    assert analysis.self_rows == []
    assert analysis.cumulative_rows == []
    assert analysis.relationship_rows == []
    assert analysis.thread_rows == []
    assert analysis.attributed_wall_ns == 0


# PRF-018: Focused analysis.
def test_analysis_filters_thread_file_function_caller_and_callee():
    filters = analyzer_model.AnalysisFilters(
        thread_ids=frozenset({43}),
        filename="validator.py",
        function="validate",
        caller="compile",
        callee="validate",
        compiler_only=True,
    )

    analysis = _analyze_wall(_controlled_profile(), filters)

    assert [row.identity.function for row in analysis.self_function_rows] == [
        "validate_graph"
    ]
    assert len(analysis.relationship_rows) == 1
    assert analysis.relationship_rows[0].caller.function == "compile_source"
    assert analysis.relationship_rows[0].callee.function == "validate_graph"
    assert [row.os_thread_id for row in analysis.thread_rows] == [43]


# PRF-018: Focused analysis.
def test_compiler_only_uses_the_runfile_relative_source_path():
    profile = _controlled_profile()
    profile.frames[4] = {
        "frame_id": 4,
        "filename": (
            "/repo/define/bazel-bin/define/compiler/main.runfiles/"
            ".main.venv/lib/python/site-packages/click/core.py"
        ),
        "function": "invoke",
        "line": 907,
    }
    first_observation = profile.observations[0]
    assert first_observation["status"] == "successful"
    first_observation["threads"][0]["stack"].insert(0, 4)

    analysis = _analyze_wall(
        profile,
        analyzer_model.AnalysisFilters(compiler_only=True),
    )

    assert "invoke" not in [
        row.identity.function for row in analysis.cumulative_function_rows
    ]


# PRF-018: Focused analysis.
def test_analysis_excludes_every_nonmatching_filter_dimension():
    missing_function = _analyze_wall(
        _controlled_profile(),
        analyzer_model.AnalysisFilters(function="not_a_function"),
    )
    missing_caller = _analyze_wall(
        _controlled_profile(),
        analyzer_model.AnalysisFilters(caller="not_a_caller"),
    )
    missing_callee = _analyze_wall(
        _controlled_profile(),
        analyzer_model.AnalysisFilters(callee="not_a_callee"),
    )

    assert missing_function.self_rows == []
    assert missing_function.cumulative_rows == []
    assert missing_function.self_function_rows == []
    assert missing_function.cumulative_function_rows == []
    assert missing_function.stack_path_rows == []
    assert missing_function.relationship_rows == []
    assert missing_caller.relationship_rows == []
    assert missing_callee.relationship_rows == []


# PRF-027: Incremental persistence.
def test_load_retains_complete_records_before_truncated_tail(tmp_path: Path):
    profile_path = tmp_path / "partial.jsonl"
    complete_records = _wire_records(_controlled_profile())[:-1]
    _ = profile_path.write_text(
        "".join(json.dumps(record) + "\n" for record in complete_records)
        + '{"record_type":"observation"',
        encoding="utf-8",
    )

    profile = schema.load(profile_path)

    assert profile.complete is False
    assert profile.success is False
    assert len(profile.observations) == 3
    assert profile.compiler_exit_status is None
    assert profile.diagnostics_status == "unknown"
    analysis = _analyze_wall(profile)
    assert analysis.wall_window_ns == 0


# PRF-020: Machine and human interfaces.
def test_rejects_superseded_schema(tmp_path: Path):
    profile_path = tmp_path / "profile.jsonl"
    records = _wire_records(_controlled_profile())
    header = records[0]
    assert header["record_type"] == "header"
    header["schema_version"] = 1
    _write_records(profile_path, records)

    result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--profile", str(profile_path)],
    )

    assert result.exit_code == 1
    assert "Error: unsupported profiler schema version: 1" in result.output


# PRF-014: CPU mode. PRF-018: Focused analysis.
# PRF-020: Machine and human interfaces.
# PRF-047: Multi-threaded critical path.
def test_help_describes_filters_and_attribution_semantics():
    result = click.testing.CliRunner().invoke(
        analyzer.main,
        ["--help"],
        terminal_width=100,
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "--thread" in help_text
    assert "--caller" in help_text
    assert "--callee" in help_text
    assert "--compiler-only" in help_text
    assert "Wall work is sampled running time" in help_text
    assert "uncertain is time whose producer or stack was not resolved" in help_text
    assert "Occupancy unions sampled intervals and rows overlap" in help_text
    assert "CPU rows report additive external scheduler runtime" in help_text
    assert "Filters affect attribution rows" in help_text
    assert "Sample hits and endpoints are observations, not calls" in help_text
