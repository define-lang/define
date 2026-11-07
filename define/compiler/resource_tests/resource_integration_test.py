"""Compiler resource regressions across retained state and adversarial workloads."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pytest

from define.compiler.resource_tests import resource_cases, resource_test_runner
from tools import runfiles

if TYPE_CHECKING:
    from pathlib import Path, PurePosixPath

_MIB = 1024**2
_CPU_SAFETY_SECONDS = 10
_CPU_GROWTH_SAFETY_SECONDS = 30
_WALL_SAFETY_SECONDS = 20
_WALL_GROWTH_SAFETY_SECONDS = 45


def _measure(
    source: Path,
    directory: Path,
    *,
    filesystem: bool,
    workers: int,
    cpu_limit: int,
    data_mib: int,
    wall_limit: int,
) -> resource_test_runner.Measurement:
    directory.mkdir()
    command = [
        str(runfiles.resolve_from_env("MAIN_BINARY")),
        "compile",
        "--max-threads",
        str(workers),
        "--out",
        str(directory / "generated"),
    ]
    if filesystem:
        command.append(source.name)
    stdin = None if filesystem else source
    artifacts = directory / "resources"
    return resource_test_runner.run(
        command,
        supervisor=runfiles.resolve_from_env("RESOURCE_TEST_RUNNER"),
        limiter=runfiles.resolve_from_env("RESOURCE_LIMIT_RUNNER"),
        directory=source.parent,
        artifacts=artifacts,
        source=stdin,
        cpu_seconds=cpu_limit,
        data_bytes=data_mib * _MIB,
        wall_seconds=wall_limit,
    )


def _stderr(directory: Path) -> str:
    return (directory / "resources" / "stderr").read_text(encoding="utf-8")


def _compiler_resource(path: PurePosixPath) -> Path:
    directory = resource_cases.COMPILER_RESOURCES_DIRECTORY
    return runfiles.resolve(f"_main/{directory / path}")


@pytest.mark.parametrize(
    "case",
    resource_cases.RETAINED_MEMORY_CASES,
    ids=[case.name for case in resource_cases.RETAINED_MEMORY_CASES],
)
def test_retained_memory(case: resource_cases.RetainedMemoryCase, tmp_path: Path):
    directory = tmp_path / "compilation"
    measured = _measure(
        _compiler_resource(case.source),
        directory,
        filesystem=case.filesystem,
        workers=4,
        cpu_limit=_CPU_SAFETY_SECONDS,
        data_mib=512,
        wall_limit=_WALL_SAFETY_SECONDS,
    )
    stderr = _stderr(directory)
    measured.check(rss_bytes=case.rss_mib * _MIB, stderr=stderr)
    assert stderr == ""


@pytest.mark.parametrize(
    "case",
    resource_cases.CPU_GROWTH_CASES,
    ids=[case.name for case in resource_cases.CPU_GROWTH_CASES],
)
def test_cpu_growth(case: resource_cases.CpuGrowthCase, tmp_path: Path):
    expected_returncode = 1 if case.expect_diagnostics else 0
    control_directory = tmp_path / "control"
    control = _measure(
        _compiler_resource(case.control),
        control_directory,
        filesystem=case.filesystem,
        workers=1,
        cpu_limit=_CPU_GROWTH_SAFETY_SECONDS,
        data_mib=1024,
        wall_limit=_WALL_GROWTH_SAFETY_SECONDS,
    )
    control_stderr = _stderr(control_directory)
    control.check(
        rss_bytes=384 * _MIB,
        stderr=control_stderr,
        expected_returncode=expected_returncode,
    )
    if case.expect_diagnostics:
        assert control_stderr != ""
    else:
        assert control_stderr == ""

    # Stop shortly after excessive growth can be established on this machine.
    # The whole-second CPU limit must exceed the relative allowance.
    cpu_limit = math.floor(control.cpu_seconds * case.maximum_ratio) + 1
    directory = tmp_path / "adversarial"
    measured = _measure(
        _compiler_resource(case.source),
        directory,
        filesystem=case.filesystem,
        workers=1,
        cpu_limit=cpu_limit,
        data_mib=1024,
        wall_limit=max(_WALL_GROWTH_SAFETY_SECONDS, cpu_limit * 2),
    )
    stderr = _stderr(directory)
    measured.check_cpu_growth(
        control,
        maximum_ratio=case.maximum_ratio,
        rss_bytes=384 * _MIB,
        stderr=stderr,
        expected_returncode=expected_returncode,
    )
    if case.expect_diagnostics:
        assert stderr != ""
    else:
        assert stderr == ""
