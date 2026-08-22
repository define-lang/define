from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import shutil
import subprocess
import sys
import typing
from unittest import mock

import pytest
from click import testing

from tools.profiler import (
    analyzer,
    analyzer_model,
    perf_analyzer,
    perf_profiler,
    perf_test_support,
    profiler,
)

if typing.TYPE_CHECKING:
    from pathlib import Path


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
        "target_pid": 999_999_999,
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
            "unresolved_python_frame_count": 0,
        }
    ]


def test_adds_perf_option_to_isolated_bazel_python_launcher(tmp_path: Path):
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
        .endswith('exec "python3" -X perf -B -I compiler.py "$@"\n')
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


def test_adds_perf_option_to_native_bazel_python_launcher(tmp_path: Path):
    launcher_path = tmp_path / "bazel-bin/tools/compiler"
    launcher_path.parent.mkdir(parents=True)
    _ = launcher_path.write_bytes(b"\xff")
    runfiles_path = launcher_path.with_name("compiler.runfiles")
    interpreter_path = runfiles_path / "_main/tools/._compiler.venv/bin/python"
    interpreter_path.parent.mkdir(parents=True)
    _ = interpreter_path.write_bytes(b"")
    main_path = runfiles_path / "_main/tools/compiler.py"
    main_path.parent.mkdir(parents=True, exist_ok=True)
    _ = main_path.write_text("", encoding="utf-8")

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(launcher_path), "compile"),
        tmp_path,
        {},
    )

    assert command == (
        str(interpreter_path),
        "-X",
        "perf",
        "-B",
        "-I",
        str(main_path),
        "compile",
    )


def test_leaves_unresolved_native_launcher_unchanged(tmp_path: Path):
    launcher_path = tmp_path / "compiler"
    _ = launcher_path.write_bytes(b"\xff")

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(launcher_path), "compile"),
        tmp_path,
        {"RUNFILES_DIR": str(tmp_path / "other.runfiles")},
    )

    assert command == (str(launcher_path), "compile")


def test_leaves_native_launcher_without_environment_files_unchanged(tmp_path: Path):
    runfiles_path = tmp_path / "compiler.runfiles"
    launcher_path = runfiles_path / "_main/tools/compiler"
    launcher_path.parent.mkdir(parents=True)
    _ = launcher_path.write_bytes(b"\xff")

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(launcher_path), "compile"),
        tmp_path,
        {"RUNFILES_DIR": str(runfiles_path)},
    )

    assert command == (str(launcher_path), "compile")


def test_finds_recorded_python_map_and_existing_native_objects(tmp_path: Path):
    runtime_map_path = perf_profiler.runtime_python_map_path(123)
    existing_object_path = tmp_path / "existing.so"
    _ = existing_object_path.write_bytes(b"ELF")
    missing_object_path = tmp_path / "missing.so"
    buildid_output = (
        "\n"
        + f"                                         {runtime_map_path}\n"
        + "                                         /python/without/buildid\n"
        + f"abc123 {existing_object_path}\n"
        + f"def456 {missing_object_path}\n"
    )

    recorded_python_map, native_objects = perf_profiler._native_objects(  # pyright: ignore[reportPrivateUsage]
        buildid_output, runtime_map_path
    )
    missing_map, no_native_objects = perf_profiler._native_objects(  # pyright: ignore[reportPrivateUsage]
        "", runtime_map_path
    )

    assert recorded_python_map is True
    assert native_objects == [str(existing_object_path)]
    assert missing_map is False
    assert no_native_objects == []


def test_replaces_stale_buildid_cache_when_there_are_no_native_objects(
    tmp_path: Path,
):
    profile_path = tmp_path / "perf.data"
    retained_buildid_path = perf_profiler.buildid_path(profile_path)
    retained_buildid_path.mkdir()
    _ = (retained_buildid_path / "stale").write_text("stale", encoding="utf-8")
    with mock.patch.object(subprocess, "run", autospec=True) as run:
        perf_profiler._retain_native_objects(  # pyright: ignore[reportPrivateUsage]
            "perf", profile_path, []
        )

    assert list(retained_buildid_path.iterdir()) == []
    run.assert_not_called()


def test_skips_real_perf_tests_when_perf_is_not_installed(tmp_path: Path):
    with (
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            return_value=None,
        ),
        pytest.raises(pytest.skip.Exception, match="Linux perf is not installed"),
    ):
        perf_test_support.require_perf_recording(tmp_path)


def test_skips_real_perf_tests_when_perf_cannot_record(tmp_path: Path):
    failed = subprocess.CompletedProcess(
        ("perf", "record"),
        255,
        stdout="",
        stderr="perf access is denied\n",
    )
    with (
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            return_value="/usr/bin/perf",
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=failed,
        ) as run,
        pytest.raises(
            pytest.skip.Exception,
            match=r"Linux perf recording is unavailable.*perf access is denied",
        ),
    ):
        perf_test_support.require_perf_recording(tmp_path)

    run.assert_called_once()


def test_skips_real_perf_tests_when_perf_fails_without_a_diagnostic(
    tmp_path: Path,
):
    failed = subprocess.CompletedProcess(
        ("perf", "record"),
        255,
        stdout="",
        stderr="",
    )
    with (
        mock.patch.object(
            shutil,
            "which",
            autospec=True,
            return_value="/usr/bin/perf",
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=failed,
        ),
        pytest.raises(
            pytest.skip.Exception,
            match=r"Linux perf recording is unavailable \(status 255\)$",
        ),
    ):
        perf_test_support.require_perf_recording(tmp_path)


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


def test_marks_unresolved_perf_map_frames_as_python_attribution_anomalies():
    script = """python 101/102 1003009 cpu-clock:u:
        7f01 [unknown] (/tmp/perf-101.map)
        7f02 py::caller:/workspace/example.py (/tmp/perf-101.map)

"""

    samples = list(
        perf_analyzer._parse_script_lines(  # pyright: ignore[reportPrivateUsage]
            script.splitlines()
        )
    )

    assert len(samples) == 1
    assert samples[0].unresolved_python_frame_count == 1
    assert samples[0].python_stack_leaf_first[0].function == "caller"


def test_reports_perf_script_failure(tmp_path: Path):
    profile_path = tmp_path / "perf.data"
    _ = perf_profiler.python_map_path(profile_path).write_text(
        "100 10 py::work:/workspace/example.py\n", encoding="utf-8"
    )
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
            profile_path, 999_999_999
        )


def test_decodes_all_threads_with_one_symbol_map(tmp_path: Path):
    profile_path = tmp_path / "perf.data"
    _ = perf_profiler.python_map_path(profile_path).write_text(
        "100 10 py::work:/workspace/example.py\n", encoding="utf-8"
    )
    decoded = mock.Mock(
        returncode=0,
        stdout=(
            "python 101/102 1003009 cpu-clock:u:\n"
            "  7f02 py::first:/workspace/example.py (/tmp/perf-101.map)\n"
            "python 101/103 1003009 cpu-clock:u:\n"
            "  7f03 py::second:/workspace/example.py (/tmp/perf-101.map)\n"
        ),
        stderr="shared warning\n",
    )
    with mock.patch.object(
        subprocess,
        "run",
        autospec=True,
        return_value=decoded,
    ) as run:
        samples, warnings = perf_analyzer._decode(  # pyright: ignore[reportPrivateUsage]
            profile_path, 999_999_999
        )

    assert [sample.os_thread_id for sample in samples] == [102, 103]
    assert [sample.python_stack_leaf_first[0].function for sample in samples] == [
        "first",
        "second",
    ]
    assert warnings == ["shared warning"]
    assert len(run.call_args_list) == 1
    assert "--symfs" not in run.call_args_list[0].args[0]


def test_refuses_to_attribute_samples_with_unresolved_python_frames(
    tmp_path: Path,
):
    profile_path = tmp_path / "perf.data"
    metadata = _profile([]).metadata
    _ = perf_profiler.metadata_path(profile_path).write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    _ = perf_profiler.diagnostics_path(profile_path).write_text("", encoding="utf-8")
    unresolved_sample = perf_analyzer.Sample(
        os_thread_id=102,
        period_ns=1_003_009,
        python_stack_leaf_first=(
            analyzer_model.FunctionIdentity(
                filename="/workspace/example.py", function="caller"
            ),
        ),
        unresolved_python_frame_count=1,
    )
    with (
        mock.patch.object(
            perf_analyzer,
            "_configuration",
            autospec=True,
            return_value=("cpu-clock", 997),
        ),
        mock.patch.object(
            perf_analyzer,
            "_decode",
            autospec=True,
            return_value=([unresolved_sample], []),
        ),
        pytest.raises(
            perf_analyzer.PerfAnalysisError,
            match="refusing potentially incorrect Python attribution",
        ),
    ):
        _ = perf_analyzer.load(profile_path)


def test_refuses_to_replace_an_existing_runtime_symbol_map(tmp_path: Path):
    profile_path = tmp_path / "perf.data"
    target_pid = 999_999_998
    _ = perf_profiler.python_map_path(profile_path).write_text(
        "100 10 py::work:/workspace/example.py\n", encoding="utf-8"
    )
    runtime_map_path = perf_profiler.runtime_python_map_path(target_pid)
    with runtime_map_path.open("x", encoding="utf-8") as runtime_map_file:
        _ = runtime_map_file.write("unrelated symbols\n")
    try:
        with (
            pytest.raises(
                perf_analyzer.PerfAnalysisError,
                match="already exists",
            ),
            perf_analyzer._materialized_python_map(  # pyright: ignore[reportPrivateUsage]
                profile_path, target_pid
            ),
        ):
            pass
        assert runtime_map_path.read_text(encoding="utf-8") == "unrelated symbols\n"
    finally:
        runtime_map_path.unlink()


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


def test_reports_perf_failure_before_target_launch(tmp_path: Path):
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")

    def fail_record(
        *arguments: object, **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        diagnostics_file = typing.cast("typing.TextIO", keyword_arguments["stderr"])
        _ = diagnostics_file.write("perf is unavailable for this kernel\n")
        command = typing.cast("tuple[str, ...]", arguments[0])
        return subprocess.CompletedProcess(command, 255)

    with (
        mock.patch.object(
            perf_profiler,
            "_perf_executable",
            autospec=True,
            return_value="perf",
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            side_effect=fail_record,
        ),
        pytest.raises(
            RuntimeError,
            match="perf could not launch the target:\nperf is unavailable for this kernel",
        ),
    ):
        _ = perf_profiler.capture(
            command=(sys.executable, "-c", "pass"),
            profile_path=tmp_path / "perf.data",
            workload_path=workload_path,
            working_directory=tmp_path,
            frequency_hz=997,
        )


def test_records_real_python_cpu_samples_with_perf(tmp_path: Path):
    perf_test_support.require_perf_recording(tmp_path)
    workload_path = tmp_path / "workload.define"
    _ = workload_path.write_text("workload", encoding="utf-8")
    profile_path = tmp_path / "perf.data"

    metadata = perf_profiler.capture(
        command=(
            sys.executable,
            "-c",
            "import concurrent.futures\n"
            + "import threading\n"
            + "barrier = threading.Barrier(32)\n"
            + "def worker(task):\n"
            + "    barrier.wait()\n"
            + "    return sum(value * value for value in range(2_000_000))\n"
            + "with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:\n"
            + "    list(executor.map(worker, range(32)))\n",
        ),
        profile_path=profile_path,
        workload_path=workload_path,
        working_directory=tmp_path,
        frequency_hz=997,
    )

    assert metadata["compiler_exit_status"] == 0
    assert profile_path.read_bytes().startswith(b"PERFILE2")
    assert any(perf_profiler.buildid_path(profile_path).rglob("elf"))
    assert perf_profiler.python_map_path(profile_path).stat().st_size > 0
    assert not perf_profiler.runtime_python_map_path(metadata["target_pid"]).exists()
    assert (
        json.loads(
            perf_profiler.metadata_path(profile_path).read_text(encoding="utf-8")
        )
        == metadata
    )
    profile = perf_analyzer.load(profile_path)
    assert not perf_profiler.runtime_python_map_path(metadata["target_pid"]).exists()
    assert profile.success is True
    assert len(profile.samples) > 10
    assert all(sample.unresolved_python_frame_count == 0 for sample in profile.samples)
    analysis = perf_analyzer.analyze(profile)
    assert analysis.sampled_cpu_ns > 0
    assert analysis.python_attributed_cpu_ns / analysis.sampled_cpu_ns > 0.9
    assert sum(row.python_attributed_cpu_ns > 0 for row in analysis.thread_rows) >= 32


def test_preserves_target_diagnostics_for_unsuccessful_perf_capture(tmp_path: Path):
    perf_test_support.require_perf_recording(tmp_path)
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
