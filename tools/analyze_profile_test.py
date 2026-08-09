import json
from pathlib import Path

import click.testing

from tools import analyze_profile
from tools.profiler import schema


def _profile() -> schema.RawProfile:
    # PRF-010: Raw-data preservation. PRF-020: Machine and human interfaces.
    return {
        "schema_version": 1,
        "complete": True,
        "success": True,
        "command": ["/repo/compiler", "compile"],
        "working_directory": "/repo",
        "workload_path": "/repo/source.dfn",
        "workload_sha256": "abc123",
        "sampling": {
            "mode": "wall",
            "schedule": "one-snapshot",
            "snapshot_delay_seconds": 0.1,
            "attachment_timeout_seconds": 10.0,
        },
        "launcher_executable": {
            "path": "/usr/bin/bash",
            "device": 1,
            "inode": 2,
        },
        "python_runtime": {
            "version": "3.14.4",
            "minor_version": "3.14",
            "free_threaded": True,
            "executable": {
                "path": "/usr/bin/python3.14t",
                "device": 1,
                "inode": 3,
            },
        },
        "lifecycle": {
            "launched_ns": 1_000_000,
            "python_observed_ns": 2_000_000,
            "exited_ns": 5_000_000,
        },
        "snapshot": {
            "host_monotonic_ns": 3_000_000,
            "target_running_ns": 2_000_000,
            "pause_started_ns": 3_000_000,
            "pause_ended_ns": 4_000_000,
            "pause_duration_ns": 1_000_000,
            "process_id": 42,
            "threads": [
                {
                    "os_thread_id": 42,
                    "stopped_state": "T",
                    "stack": [
                        {
                            "filename": "/repo/compiler.py",
                            "function": "compile_source",
                            "line": 10,
                        },
                        {
                            "filename": "/repo/worker.py",
                            "function": "generate_code",
                            "line": 20,
                        },
                    ],
                },
                {
                    "os_thread_id": 43,
                    "stopped_state": "T",
                    "stack": [
                        {
                            "filename": "/repo/worker.py",
                            "function": "validate_graph",
                            "line": 30,
                        }
                    ],
                },
            ],
        },
        "failures": [],
        "observation_counts": {
            "attempted": 1,
            "successful": 1,
            "discarded": 0,
            "missed": 0,
        },
        "compiler_exit_status": 0,
        "diagnostics_status": "none",
        "interruption_signal": None,
    }


# PRF-015: Full stacks. PRF-016: Source identity.
# PRF-020: Machine and human interfaces. PRF-043: Analyzer at every checkpoint.
def test_reports_complete_snapshot(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    _ = profile_path.write_text(json.dumps(_profile()), encoding="utf-8")

    result = click.testing.CliRunner().invoke(
        analyze_profile.main, ["--profile", str(profile_path)]
    )

    assert result.exit_code == 0
    assert "Profile schema: 1; complete; successful" in result.output
    assert "Process 42: launcher /usr/bin/bash" in result.output
    assert "Python runtime: 3.14.4 free-threaded" in result.output
    assert "Snapshot: 2 Python threads; profiler pause 1.000 ms" in result.output
    assert "Thread 42 (state T):" in result.output
    assert "/repo/compiler.py:10 (compile_source)" in result.output
    assert "Files (2):" in result.output
    assert "Functions (3):" in result.output
    assert "Failures" not in result.output


# PRF-024: Explicit failures. PRF-026: No silent partial success.
# PRF-020: Machine and human interfaces.
def test_reports_incomplete_profile_without_snapshot(tmp_path: Path):
    profile = _profile()
    profile["complete"] = False
    profile["success"] = False
    profile["python_runtime"] = None
    profile["snapshot"] = None
    profile["failures"] = [
        {
            "host_monotonic_ns": 3_000_000,
            "kind": "profiler-interrupted",
            "reason": "SIGINT",
        }
    ]
    profile["observation_counts"] = {
        "attempted": 0,
        "successful": 0,
        "discarded": 0,
        "missed": 0,
    }
    profile["compiler_exit_status"] = -15
    profile["diagnostics_status"] = "present"
    profile_path = tmp_path / "profile.json"
    _ = profile_path.write_text(json.dumps(profile), encoding="utf-8")

    result = click.testing.CliRunner().invoke(
        analyze_profile.main, ["--profile", str(profile_path)]
    )

    assert result.exit_code == 0
    assert "Profile schema: 1; incomplete; unsuccessful" in result.output
    assert "Process unknown" in result.output
    assert "Python runtime: not observed" in result.output
    assert "Snapshot: unavailable" in result.output
    assert "Compiler exit status: -15; diagnostics: present" in result.output
    assert "Failures (1):" in result.output
    assert "profiler-interrupted: SIGINT" in result.output


# PRF-020: Machine and human interfaces. PRF-039: Current design only.
def test_rejects_unknown_schema(tmp_path: Path):
    profile = _profile()
    profile["schema_version"] = 2
    profile_path = tmp_path / "profile.json"
    _ = profile_path.write_text(json.dumps(profile), encoding="utf-8")

    result = click.testing.CliRunner().invoke(
        analyze_profile.main, ["--profile", str(profile_path)]
    )

    assert result.exit_code == 1
    assert "Error: unsupported profiler schema version: 2" in result.output


# PRF-020: Machine and human interfaces. PRF-043: Analyzer at every checkpoint.
def test_help_describes_snapshot_limits():
    result = click.testing.CliRunner().invoke(
        analyze_profile.main, ["--help"], terminal_width=100
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "Raw JSON profile produced" in help_text
    assert "does not infer durations, calls, or thread lifetime" in help_text
