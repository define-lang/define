import contextlib
import dataclasses
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from click import testing

from tools.profiler import (
    analyzer,
    analyzer_model,
    perf_analyzer,
    perf_profiler,
    profiler,
)


def _profile(
    weighted_functions: list[tuple[int, int, str | None]],
) -> perf_analyzer.Profile:
    samples = [
        perf_analyzer.Sample(
            os_thread_id=thread_id,
            period_ns=period_ns,
            python_stack_leaf_first=(
                analyzer_model.FunctionIdentity(
                    filename="/workspace/define/compiler/example.py",
                    function=function,
                ),
            )
            if function is not None
            else (),
        )
        for period_ns, thread_id, function in weighted_functions
    ]
    metadata: perf_profiler.Metadata = {
        "command": ["compiler"],
        "working_directory": "/workspace",
        "workload_path": "/workspace/input.define",
        "workload_sha256": "digest",
        "started_ns": 10,
        "ended_ns": 110,
        "compiler_exit_status": 0,
    }
    return perf_analyzer.Profile(
        metadata=metadata,
        event="cpu-clock",
        frequency_hz=997,
        diagnostics="",
        samples=samples,
        perf_script_warnings=[],
    )


def test_parses_perf_samples_and_python_frame_trampolines():
    script = """python 101/102 1003009 cpu-clock:u:
        7f01 native_leaf (/usr/lib/libc.so.6)
        7f02 py::leaf:/workspace/example.py (/tmp/jitted-101-1.so)
        7f03 py::caller:/workspace/example.py (/tmp/jitted-101-2.so)

"""

    samples = list(
        perf_analyzer._parse_script_lines(  # pyright: ignore[reportPrivateUsage]
            script.splitlines()
        )
    )

    assert [dataclasses.asdict(sample) for sample in samples] == [
        {
            "os_thread_id": 102,
            "period_ns": 1_003_009,
            "python_stack_leaf_first": (
                {"filename": "/workspace/example.py", "function": "leaf"},
                {"filename": "/workspace/example.py", "function": "caller"},
            ),
        }
    ]


def test_adds_perf_jit_option_to_isolated_bazel_python_launcher(tmp_path: Path):
    launcher_path = tmp_path / "compiler"
    _ = launcher_path.write_text(
        "#!/usr/bin/env bash\n"
        + "# __PEX_PY_BINARY_ENTRYPOINT__ _main/compiler.py\n"
        + 'exec "python3" -B -I compiler.py "$@"\n',
        encoding="utf-8",
    )
    environment: dict[str, str] = {}

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(launcher_path), "compile"),
        tmp_path,
        environment,
    )

    assert command == (str(tmp_path / "python-launcher"), "compile")
    assert (
        (tmp_path / "python-launcher")
        .read_text(encoding="utf-8")
        .endswith('exec "python3" -X perf_jit -B -I compiler.py "$@"\n')
    )
    assert environment["RUNFILES_DIR"] == str(tmp_path / "compiler.runfiles")


def test_leaves_non_bazel_command_unchanged(tmp_path: Path):
    executable_path = tmp_path / "compiler"
    _ = executable_path.write_text("native executable", encoding="utf-8")
    environment: dict[str, str] = {}

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(executable_path), "compile"),
        tmp_path,
        environment,
    )

    assert command == (str(executable_path), "compile")
    assert environment == {}
    assert (
        list(
            perf_analyzer._parse_script_lines(  # pyright: ignore[reportPrivateUsage]
                []
            )
        )
        == []
    )


def test_rejects_malformed_perf_script_evidence():
    with pytest.raises(
        perf_analyzer.PerfAnalysisError,
        match="malformed perf script line",
    ):
        _ = list(
            perf_analyzer._parse_script_lines(  # pyright: ignore[reportPrivateUsage]
                ["unexpected perf output"]
            )
        )

    with pytest.raises(
        perf_analyzer.PerfAnalysisError,
        match="malformed Python perf symbol",
    ):
        _ = list(
            perf_analyzer._parse_script_lines(  # pyright: ignore[reportPrivateUsage]
                [
                    "python 101/102 1003009 cpu-clock:u:",
                    "  7f02 py::malformed (/tmp/jitted-101-1.so)",
                ]
            )
        )


def test_reports_perf_script_failure(tmp_path: Path):
    failed = mock.Mock(returncode=1, stdout="", stderr="decode failed\n")
    with (
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=failed,
        ),
        pytest.raises(perf_analyzer.PerfAnalysisError, match="decode failed"),
    ):
        _ = perf_analyzer._decode(  # pyright: ignore[reportPrivateUsage]
            tmp_path / "perf.data"
        )


def test_decodes_each_thread_separately(tmp_path: Path):
    discovered_threads = mock.Mock(returncode=0, stdout="102\n103\n", stderr="")
    first_thread = mock.Mock(
        returncode=0,
        stdout=(
            "python 101/102 1003009 cpu-clock:u:\n"
            "  7f02 py::first:/workspace/example.py (/tmp/jitted-101-1.so)\n"
        ),
        stderr="shared warning\n",
    )
    second_thread = mock.Mock(
        returncode=0,
        stdout=(
            "python 101/103 1003009 cpu-clock:u:\n"
            "  7f03 py::second:/workspace/example.py (/tmp/jitted-101-2.so)\n"
        ),
        stderr="\nshared warning\n",
    )
    with mock.patch.object(
        subprocess,
        "run",
        autospec=True,
        side_effect=[discovered_threads, first_thread, second_thread],
    ) as run:
        samples, warnings = perf_analyzer._decode(  # pyright: ignore[reportPrivateUsage]
            tmp_path / "perf.data"
        )

    assert [sample.os_thread_id for sample in samples] == [102, 103]
    assert [sample.python_stack_leaf_first[0].function for sample in samples] == [
        "first",
        "second",
    ]
    assert warnings == ["shared warning"]
    assert [call.args[0][6:8] for call in run.call_args_list[1:]] == [
        ("--tid", "102"),
        ("--tid", "103"),
    ]


def test_cpu_percentages_include_native_and_filtered_python_samples():
    profile = _profile(
        [
            (50, 1, "compiler_work"),
            (30, 2, "lark_work"),
            (20, 2, None),
        ]
    )

    analysis = perf_analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(function="compiler_work"),
    )

    assert analysis.sampled_cpu_ns == 100
    assert analysis.python_attributed_cpu_ns == 80
    assert analysis.unattributed_cpu_ns == 20
    assert len(analysis.self_function_rows) == 1
    assert analysis.self_function_rows[0].cpu_time_ns == 50
    assert analysis.self_function_rows[0].percentage == 50.0


def test_filters_perf_relationships_and_threads():
    profile = _profile([(100, 1, "leaf"), (50, 2, "other")])
    caller = analyzer_model.FunctionIdentity(
        filename="/workspace/define/compiler/example.py",
        function="caller",
    )
    profile.samples[0] = dataclasses.replace(
        profile.samples[0],
        python_stack_leaf_first=(*profile.samples[0].python_stack_leaf_first, caller),
    )

    caller_filtered = perf_analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(caller="missing"),
    )
    callee_filtered = perf_analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(callee="missing"),
    )
    file_filtered = perf_analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(filename="missing"),
    )
    thread_filtered = perf_analyzer.analyze(
        profile,
        analyzer_model.AnalysisFilters(thread_ids=frozenset({2})),
    )

    assert caller_filtered.relationship_rows == []
    assert callee_filtered.relationship_rows == []
    assert file_filtered.relationship_rows == []
    assert [row.os_thread_id for row in thread_filtered.thread_rows] == [2]
    assert {row.identity.function for row in thread_filtered.self_function_rows} == {
        "other"
    }


def test_reports_perf_warnings():
    profile = dataclasses.replace(
        _profile([(100, 1, "compile")]),
        perf_script_warnings=["sample warning"],
    )
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        perf_analyzer.emit_report(profile, perf_analyzer.analyze(profile), 5)

    assert "Perf script warnings:\n  sample warning" in output.getvalue()


def test_analyzer_dispatches_native_perf_data(tmp_path: Path):
    profile_path = tmp_path / "perf.data"
    _ = profile_path.write_bytes(b"PERFILE2")
    profile = _profile([(100, 7, "compile")])
    with mock.patch.object(
        perf_analyzer,
        "load",
        autospec=True,
        return_value=profile,
    ):
        result = testing.CliRunner().invoke(
            analyzer.main,
            ("--profile", str(profile_path)),
        )

    assert result.exit_code == 0
    assert "Native perf profile: complete; successful" in result.output
    assert "100.00%" in result.output


def test_cpu_command_dispatches_to_perf(tmp_path: Path):
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")
    metadata = _profile([(100, 1, "compile")]).metadata
    profile_path = tmp_path / "perf.data"
    _ = perf_profiler.diagnostics_path(profile_path).write_text("", encoding="utf-8")
    with mock.patch.object(
        perf_profiler,
        "capture",
        autospec=True,
        return_value=metadata,
    ) as capture:
        result = testing.CliRunner().invoke(
            profiler.main,
            (
                "--mode",
                "cpu",
                "--profile",
                str(profile_path),
                "--workload",
                str(workload_path),
                "--working-directory",
                str(tmp_path),
                "--",
                "compiler",
            ),
        )

    assert result.exit_code == 0
    assert "Capture: complete; successful; compiler exit 0" in result.output
    capture.assert_called_once()


def test_cpu_command_rejects_wall_coordination_descriptor(tmp_path: Path):
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")

    result = testing.CliRunner().invoke(
        profiler.main,
        (
            "--mode",
            "cpu",
            "--profile",
            str(tmp_path / "perf.data"),
            "--workload",
            str(workload_path),
            "--event-fd",
            "1",
            "--",
            "compiler",
        ),
    )

    assert result.exit_code == 2
    assert "--event-fd is supported only in wall mode" in result.output


def test_records_real_python_cpu_samples_with_perf(tmp_path: Path):
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")
    profile_path = tmp_path / "perf.data"

    metadata = perf_profiler.capture(
        command=(
            sys.executable,
            "-c",
            "from concurrent.futures import ThreadPoolExecutor; "
            + "executor = ThreadPoolExecutor(max_workers=2); "
            + "list(executor.map(lambda _: sum(value * value for value in "
            + "range(8_000_000)), range(2)))",
        ),
        profile_path=profile_path,
        workload_path=workload_path,
        working_directory=tmp_path,
        frequency_hz=997,
    )

    assert metadata["compiler_exit_status"] == 0
    assert profile_path.read_bytes().startswith(b"PERFILE2")
    assert any(perf_profiler.buildid_path(profile_path).rglob("elf"))
    assert (
        json.loads(
            perf_profiler.metadata_path(profile_path).read_text(encoding="utf-8")
        )
        == metadata
    )
    profile = perf_analyzer.load(profile_path)
    assert profile.success is True
    assert len(profile.samples) > 10
    analysis = perf_analyzer.analyze(profile)
    assert analysis.sampled_cpu_ns > 0
    assert analysis.python_attributed_cpu_ns > 0
    assert sum(row.python_attributed_cpu_ns > 0 for row in analysis.thread_rows) >= 2


def test_preserves_target_diagnostics_for_unsuccessful_perf_capture(tmp_path: Path):
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")
    profile_path = tmp_path / "perf.data"
    diagnostics = io.StringIO()
    with contextlib.redirect_stderr(diagnostics):
        metadata = perf_profiler.capture(
            command=(
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('target diagnostic\\n'); "
                + "sum(value * value for value in range(4_000_000))",
            ),
            profile_path=profile_path,
            workload_path=workload_path,
            working_directory=tmp_path,
            frequency_hz=997,
        )

    assert metadata["compiler_exit_status"] == 0
    assert (
        profile_path.with_name(profile_path.name + ".stderr").read_text(
            encoding="utf-8"
        )
        == "target diagnostic\n"
    )
    assert diagnostics.getvalue() == "target diagnostic\n"
