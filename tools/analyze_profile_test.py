import json
from pathlib import Path

import click.testing
import pytest

from tools import analyze_profile


def _event(
    phase: str,
    timestamp: int,
    thread: int,
    name: str,
    line: int,
    filename: str = "/repo/compiler.py",
) -> dict[str, object]:
    return {
        "args": {"filename": filename, "line": line},
        "cat": "py-spy",
        "name": name,
        "ph": phase,
        "pid": 1,
        "tid": thread,
        "ts": timestamp,
    }


@pytest.fixture
def profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "profile.json"
    _ = path.write_text(
        json.dumps(
            [
                _event("B", 0, 1, "compile", 1),
                _event("B", 0, 1, "work", 2),
                _event("B", 500_000, 2, "worker", 3),
                _event("B", 500_000, 2, "work", 2),
                _event("E", 1_000_000, 1, "work", 2),
                _event("B", 1_000_000, 1, "wait", 4),
                _event("E", 2_000_000, 1, "wait", 4),
                _event("B", 2_000_000, 1, "work", 2),
                _event("E", 2_500_000, 2, "work", 2),
                _event("E", 2_500_000, 2, "worker", 3),
                _event("E", 3_000_000, 1, "work", 2),
                _event("E", 3_000_000, 1, "compile", 1),
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def cpu_profile_path(tmp_path: Path) -> Path:
    path = tmp_path / "cpu_profile.json"
    raw_samples = """compile (/repo/compiler.py:1);work (/repo/compiler.py:2) 100
compile (/repo/compiler.py:1);wait (/repo/compiler.py:4) 100
compile (/repo/compiler.py:1);work (/repo/compiler.py:2) 100
worker (/repo/compiler.py:3);work (/repo/compiler.py:9) 200
[No Python frame] 70
 30"""
    _ = path.write_text(
        json.dumps(
            {
                "format": "define-py-spy-cpu-v1",
                "wall_time_seconds": 3.0,
                "raw_samples": raw_samples,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_loads_timestamped_segments(profile_path: Path):
    wall_time, thread_count, segments = analyze_profile.load_segments(profile_path)

    assert wall_time == 3.0
    assert thread_count == 2
    assert segments == [
        (
            (
                ("/repo/compiler.py", 1, "compile"),
                ("/repo/compiler.py", 2, "work"),
            ),
            0.0,
            1.0,
        ),
        (
            (
                ("/repo/compiler.py", 1, "compile"),
                ("/repo/compiler.py", 4, "wait"),
            ),
            1.0,
            2.0,
        ),
        (
            (
                ("/repo/compiler.py", 1, "compile"),
                ("/repo/compiler.py", 2, "work"),
            ),
            2.0,
            3.0,
        ),
        (
            (
                ("/repo/compiler.py", 3, "worker"),
                ("/repo/compiler.py", 2, "work"),
            ),
            0.5,
            2.5,
        ),
    ]


def test_unions_wall_metrics_across_threads(profile_path: Path):
    _wall_time, _thread_count, segments = analyze_profile.load_segments(profile_path)

    metrics = analyze_profile.wall_metrics(segments)

    assert metrics[("/repo/compiler.py", 2, "work")] == (3.0, 3.0, 3.0)
    assert metrics[("/repo/compiler.py", 4, "wait")] == (1.0, 1.0, 1.0)
    assert metrics[("/repo/compiler.py", 1, "compile")] == (0.0, 3.0, 3.0)


def test_unions_disjoint_wall_intervals():
    function = ("/repo/compiler.py", 1, "compile")

    metrics = analyze_profile.wall_metrics(
        [((function,), 0.0, 1.0), ((function,), 2.0, 4.0)]
    )

    assert metrics[function] == (3.0, 3.0, 2.0)


def test_wall_segments_normalize_current_lines_for_function_identity(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    _ = profile_path.write_text(
        json.dumps(
            [
                _event("B", 0, 1, "compile", 10),
                _event("E", 1_000_000, 1, "compile", 10),
                _event("B", 2_000_000, 1, "compile", 20),
                _event("E", 3_000_000, 1, "compile", 20),
            ]
        ),
        encoding="utf-8",
    )

    _wall_time, _thread_count, segments = analyze_profile.load_segments(profile_path)

    assert segments == [
        ((("/repo/compiler.py", 10, "compile"),), 0.0, 1.0),
        ((("/repo/compiler.py", 10, "compile"),), 2.0, 3.0),
    ]


def test_loads_weighted_cpu_samples_and_omits_missing_python_stack(
    cpu_profile_path: Path,
):
    wall_time, sample_count, omitted_samples, samples = (
        analyze_profile.load_cpu_samples(cpu_profile_path)
    )

    assert wall_time == 3.0
    assert sample_count == 500
    assert omitted_samples == 100
    assert samples[0] == (
        (
            ("/repo/compiler.py", 1, "compile"),
            ("/repo/compiler.py", 2, "work"),
        ),
        1.0,
    )


def test_loads_cpu_frames_without_numeric_line_numbers(tmp_path: Path):
    profile_path = tmp_path / "cpu_profile.json"
    _ = profile_path.write_text(
        json.dumps(
            {
                "format": "define-py-spy-cpu-v1",
                "wall_time_seconds": 1.0,
                "raw_samples": (
                    "native frame;compile (/repo/compiler.py:not-a-line) 100"
                ),
            }
        ),
        encoding="utf-8",
    )

    _wall_time, _sample_count, _omitted_samples, samples = (
        analyze_profile.load_cpu_samples(profile_path)
    )

    assert samples == [
        (
            (
                ("", 0, "native frame"),
                ("/repo/compiler.py:not-a-line", 0, "compile"),
            ),
            1.0,
        )
    ]


def test_sums_weighted_cpu_metrics(cpu_profile_path: Path):
    _wall_time, _sample_count, _omitted_samples, samples = (
        analyze_profile.load_cpu_samples(cpu_profile_path)
    )

    metrics = analyze_profile.cpu_metrics(samples)

    assert metrics[("/repo/compiler.py", 2, "work")] == (4.0, 4.0)
    assert metrics[("/repo/compiler.py", 1, "compile")] == (0.0, 3.0)
    assert metrics[("/repo/compiler.py", 3, "worker")] == (0.0, 2.0)


def test_limits_compiler_view_to_define_compiler_sources():
    metrics = {
        ("/runfiles/_main/define/compiler/driver.py", 1, "run"): (1.0, 1.0, 1.0),
        ("/projects/define/define/compiler/parser.py", 2, "parse"): (2.0, 2.0, 2.0),
        (
            "/projects/define/bazel-bin/define/compiler/main.runfiles/site/click.py",
            3,
            "invoke",
        ): (3.0, 3.0, 3.0),
    }

    assert analyze_profile.compiler_metrics(metrics) == {
        ("/runfiles/_main/define/compiler/driver.py", 1, "run"): (1.0, 1.0, 1.0),
        ("/projects/define/define/compiler/parser.py", 2, "parse"): (2.0, 2.0, 2.0),
    }


def test_removes_complete_excluded_subtree():
    lark = ("/repo/lark_standalone.py", 1, "parse")
    validate = ("/repo/validator.py", 2, "validate")
    samples = [((lark, validate), 1.0), ((validate,), 1.0)]

    assert analyze_profile.without_file(samples, "lark_standalone.py") == [
        ((validate,), 1.0)
    ]


def test_main_makes_wall_report_primary(profile_path: Path):
    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        ["--profile", str(profile_path), "--top", "1"],
    )

    assert result.exit_code == 0
    assert "Wall time: 3.000s; sampled threads: 2; functions: 4" in result.output
    assert "=== PYTHON WALL (top 1 by self) ===" in result.output
    assert "=== PYTHON WALL (top 1 by longest) ===" in result.output
    assert "=== PYTHON WALL (top 1 by cumulative) ===" in result.output


def test_main_reports_define_compiler_wall_metrics(tmp_path: Path):
    profile_path = tmp_path / "profile.json"
    compiler_file = "/projects/define/define/compiler/driver.py"
    _ = profile_path.write_text(
        json.dumps(
            [
                _event("B", 0, 1, "compile", 1, compiler_file),
                _event("E", 1_000_000, 1, "compile", 1, compiler_file),
            ]
        ),
        encoding="utf-8",
    )

    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        ["--profile", str(profile_path), "--top", "1"],
    )

    assert result.exit_code == 0
    assert "=== DEFINE COMPILER WALL (top 1 by self) ===" in result.output
    assert "=== DEFINE COMPILER WALL (top 1 by longest) ===" in result.output


def test_main_reports_cpu_time(cpu_profile_path: Path):
    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        [
            "--profile",
            str(cpu_profile_path),
            "--profile-mode",
            "cpu",
            "--top",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert (
        "Attributed CPU time: 5.000s; wall time: 3.000s; active Python samples: 500"
        in result.output
    )
    assert "Omitted samples without a Python stack: 100" in result.output
    assert "Non-Lark work: 5.000s sampled time (100.0%)" in result.output
    assert "=== PYTHON (top 1 by self) ===" in result.output


def test_main_reports_define_compiler_cpu_without_omission_notice(tmp_path: Path):
    profile_path = tmp_path / "cpu_profile.json"
    _ = profile_path.write_text(
        json.dumps(
            {
                "format": "define-py-spy-cpu-v1",
                "wall_time_seconds": 1.0,
                "raw_samples": (
                    "compile (/projects/define/define/compiler/driver.py:1) 100"
                ),
            }
        ),
        encoding="utf-8",
    )

    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        ["--profile", str(profile_path), "--profile-mode", "cpu", "--top", "1"],
    )

    assert result.exit_code == 0
    assert "Omitted samples without a Python stack" not in result.output
    assert "=== DEFINE COMPILER (top 1 by self) ===" in result.output
    assert "=== DEFINE COMPILER (top 1 by cumulative) ===" in result.output


def test_help_explains_report_semantics():
    result = click.testing.CliRunner().invoke(
        analyze_profile.main, ["--help"], terminal_width=100
    )

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "Pass the same --profile-mode used when recording the profile." in (
        help_text
    )
    assert "Function wall rows can overlap and must not be added together." in (
        help_text
    )
    assert "CPU time can exceed wall time under parallel execution." in help_text
    assert "Samples without a Python stack are omitted from CPU totals." in (help_text)


def test_handles_empty_trace(tmp_path: Path):
    profile_path = tmp_path / "empty.json"
    _ = profile_path.write_text("[]", encoding="utf-8")

    result = click.testing.CliRunner().invoke(
        analyze_profile.main,
        ["--profile", str(profile_path), "--top", "1"],
    )

    assert result.exit_code == 0
    assert "Wall time: 0.000s; sampled threads: 0; functions: 0" in result.output
