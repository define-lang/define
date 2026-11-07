from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from tools.profiler import perf_access, perf_profiler, perf_test_support

if TYPE_CHECKING:
    from pathlib import Path


def test_adds_perf_option_to_isolated_bazel_python_launcher(tmp_path: Path):
    launcher_path = tmp_path / "compiler"
    _ = launcher_path.write_text(
        "#!/usr/bin/env bash\n"
        + "# __PEX_PY_BINARY_ENTRYPOINT__ _main/compiler.py\n"
        + 'exec "python3" -B -I compiler.py "$@"\n',
        encoding="utf-8",
        newline="\n",
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
    _ = executable_path.write_text("native executable", encoding="utf-8", newline="\n")
    environment: dict[str, str] = {}

    command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
        (str(executable_path), "compile"),
        tmp_path,
        environment,
    )

    assert command == (str(executable_path), "compile")
    assert environment == {}


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
    _ = main_path.write_text("", encoding="utf-8", newline="\n")

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

    for environment in ({}, {"RUNFILES_DIR": str(tmp_path / "other.runfiles")}):
        command = perf_profiler._profiled_command(  # pyright: ignore[reportPrivateUsage]
            (str(launcher_path), "compile"),
            tmp_path,
            environment,
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


def test_reports_missing_perf_access_before_target_launch(tmp_path: Path):
    profile_path = tmp_path / "stacks.txt"
    with (
        mock.patch.object(
            perf_access,
            "require_cpu_access",
            autospec=True,
            side_effect=perf_access.PerfAccessError("grant CPU access"),
        ),
        pytest.raises(perf_access.PerfAccessError, match="grant CPU access"),
    ):
        _ = perf_profiler.capture(
            command=("compiler",),
            profile_path=profile_path,
            working_directory=tmp_path,
            environment=dict(os.environ),
            stdin=None,
        )

    assert not profile_path.exists()


def test_reports_perf_failure_before_target_launch(tmp_path: Path):
    with (
        mock.patch.object(perf_access, "require_cpu_access", autospec=True),
        mock.patch.object(
            perf_access,
            "perf_executable",
            autospec=True,
            return_value="perf",
        ),
        mock.patch.object(
            subprocess,
            "run",
            autospec=True,
            return_value=subprocess.CompletedProcess(("perf",), 255),
        ),
        pytest.raises(
            RuntimeError,
            match="perf record exited with status 255 before launching the target",
        ),
    ):
        _ = perf_profiler.capture(
            command=(sys.executable, "-c", "pass"),
            profile_path=tmp_path / "stacks.txt",
            working_directory=tmp_path,
            environment=dict(os.environ),
            stdin=None,
        )


def test_records_real_python_cpu_stacks_with_perf(tmp_path: Path):
    perf_test_support.require_perf_recording(tmp_path)
    profile_path = tmp_path / "stacks.txt"

    exit_status = perf_profiler.capture(
        command=(
            sys.executable,
            "-c",
            "import concurrent.futures\n"
            + "import threading\n"
            + "barrier = threading.Barrier(32)\n"
            + "def compiler_work(task):\n"
            + "    barrier.wait()\n"
            + "    return sum(value * value for value in range(2_000_000))\n"
            + "with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:\n"
            + "    list(executor.map(compiler_work, range(32)))\n",
        ),
        profile_path=profile_path,
        working_directory=tmp_path,
        environment=dict(os.environ),
        stdin=None,
    )

    assert exit_status == 0
    work_threads: set[str] = set()
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        stack, _, count = line.rpartition(" ")
        assert int(count) > 0
        if "py::compiler_work:" in stack:
            work_threads.add(stack.split(";", maxsplit=1)[0])
    assert len(work_threads) == 32


def test_returns_target_exit_status_and_removes_its_symbol_map(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
):
    perf_test_support.require_perf_recording(tmp_path)

    exit_status = perf_profiler.capture(
        command=(
            sys.executable,
            "-c",
            "import os, sys; sys.stderr.write(f'target {os.getpid()}\\n'); "
            + "sum(value * value for value in range(4_000_000)); sys.exit(3)",
        ),
        profile_path=tmp_path / "stacks.txt",
        working_directory=tmp_path,
        environment=dict(os.environ),
        stdin=None,
    )

    assert exit_status == 3
    diagnostics = capfd.readouterr().err
    assert diagnostics.startswith("target ")
    target_pid = int(diagnostics.split()[1])
    assert not perf_profiler.runtime_python_map_path(target_pid).exists()
