"""Compiler resource regressions across retained state and adversarial workloads."""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import pytest

from define.compiler import test_runfiles
from define.compiler.resource_tests import resource_test_runner

if TYPE_CHECKING:
    from pathlib import Path

_MIB = 1024**2
_CPU_SAFETY_SECONDS = 10
_CPU_GROWTH_SAFETY_SECONDS = 30
_WALL_SAFETY_SECONDS = 20
_WALL_GROWTH_SAFETY_SECONDS = 45


@dataclasses.dataclass(kw_only=True)
class MemoryCase:
    source_variable: str
    filesystem: bool
    rss_mib: int


@dataclasses.dataclass(kw_only=True)
class CpuGrowthCase:
    control_variable: str
    source_variable: str
    filesystem: bool
    maximum_ratio: float
    # Whether both programs are expected to report diagnostics and fail.
    expect_diagnostics: bool = False


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
        str(test_runfiles.resolve_from_env("MAIN_BINARY")),
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
        supervisor=test_runfiles.resolve_from_env("RESOURCE_TEST_RUNNER"),
        limiter=test_runfiles.resolve_from_env("RESOURCE_LIMIT_RUNNER"),
        directory=source.parent,
        artifacts=artifacts,
        source=stdin,
        cpu_seconds=cpu_limit,
        data_bytes=data_mib * _MIB,
        wall_seconds=wall_limit,
    )


def _stderr(directory: Path) -> str:
    return (directory / "resources" / "stderr").read_text()


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            MemoryCase(
                source_variable="LARGE_OPERATION_VOLUME", filesystem=False, rss_mib=192
            ),
            id="large_operation_volume",
        ),
        pytest.param(
            MemoryCase(
                source_variable="DESTRUCTION_CONTRACTS", filesystem=False, rss_mib=192
            ),
            id="destruction_contracts",
        ),
        pytest.param(
            MemoryCase(
                source_variable="MANY_SUBSTANTIAL_ACTIONS",
                filesystem=False,
                rss_mib=192,
            ),
            id="many_substantial_actions",
        ),
        pytest.param(
            MemoryCase(
                source_variable="WIDE_DESTRUCTION", filesystem=False, rss_mib=192
            ),
            id="wide_destruction",
        ),
        pytest.param(
            MemoryCase(
                source_variable="REFERENCE_GRAPH_PROJECT", filesystem=True, rss_mib=192
            ),
            id="reference_graph_project",
        ),
        pytest.param(
            MemoryCase(
                source_variable="PARTICLE_OPERATIONS", filesystem=False, rss_mib=192
            ),
            id="particle_operations",
        ),
        pytest.param(
            MemoryCase(
                source_variable="GUARANTEE_EXPANSION", filesystem=False, rss_mib=192
            ),
            id="guarantee_expansion",
        ),
        pytest.param(
            MemoryCase(
                source_variable="DEEP_REQUIREMENTS", filesystem=False, rss_mib=192
            ),
            id="deep_requirements",
        ),
        pytest.param(
            MemoryCase(
                source_variable="PENDING_GUARANTEES", filesystem=False, rss_mib=384
            ),
            id="pending_guarantees",
        ),
    ],
)
def test_retained_memory(case: MemoryCase, tmp_path: Path):
    directory = tmp_path / "compilation"
    measured = _measure(
        test_runfiles.resolve_from_env(case.source_variable),
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
    [
        pytest.param(
            CpuGrowthCase(
                control_variable="PENDING_GUARANTEES_GROWTH_CONTROL",
                source_variable="PENDING_GUARANTEES_GROWTH",
                filesystem=False,
                maximum_ratio=8,
            ),
            id="pending_guarantees",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="REFERENCE_DEPTH_UPDATES_CONTROL",
                source_variable="REFERENCE_DEPTH_UPDATES",
                filesystem=True,
                maximum_ratio=2,
            ),
            id="reference_depth_updates",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="QUALITY_IMPLICATIONS_CONTROL",
                source_variable="QUALITY_IMPLICATIONS",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="shared_quality_implications",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_DESTRUCTORS_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_DESTRUCTORS",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_destructors",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_CONTRACTED_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_CONTRACTED",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_contracted",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_MOVE_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_MOVE",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_move",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_REARRANGE_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_REARRANGE",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_rearrange",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_REARRANGE_DESTRUCTORS_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_REARRANGE_DESTRUCTORS",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_rearrange_destructors",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_ERROR_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_ERROR",
                filesystem=False,
                maximum_ratio=4,
                expect_diagnostics=True,
            ),
            id="triggered_children_destruction_error",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_DEPENDENT_SIBLINGS_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_DEPENDENT_SIBLINGS",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_dependent_siblings",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_IN_DESTRUCTOR_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_IN_DESTRUCTOR",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_in_destructor",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_IN_DESTRUCTOR_CONTRACTED_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_IN_DESTRUCTOR_CONTRACTED",
                filesystem=False,
                maximum_ratio=4,
                expect_diagnostics=True,
            ),
            id="triggered_children_destruction_in_destructor_contracted",
        ),
        pytest.param(
            CpuGrowthCase(
                control_variable="TRIGGERED_CHILDREN_DESTRUCTION_SAME_PARTICLE_CONTROL",
                source_variable="TRIGGERED_CHILDREN_DESTRUCTION_SAME_PARTICLE",
                filesystem=False,
                maximum_ratio=4,
            ),
            id="triggered_children_destruction_same_particle",
        ),
    ],
)
def test_cpu_growth(case: CpuGrowthCase, tmp_path: Path):
    expected_returncode = 1 if case.expect_diagnostics else 0
    control_directory = tmp_path / "control"
    control = _measure(
        test_runfiles.resolve_from_env(case.control_variable),
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
        test_runfiles.resolve_from_env(case.source_variable),
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
