"""Programs whose compiles must stay within memory and CPU time bounds."""

from __future__ import annotations

import dataclasses
from pathlib import PurePosixPath

COMPILER_RESOURCES_DIRECTORY = PurePosixPath("define/testdata/compiler_resources")


@dataclasses.dataclass(kw_only=True)
class RetainedMemoryCase:
    """A large program whose compile must stay within a resident memory bound."""

    name: str
    # Relative to COMPILER_RESOURCES_DIRECTORY.
    source: PurePosixPath
    filesystem: bool
    rss_mib: int


def _single_file_memory_case(name: str, *, rss_mib: int = 192) -> RetainedMemoryCase:
    return RetainedMemoryCase(
        name=name,
        source=PurePosixPath(f"{name}.dfn"),
        filesystem=False,
        rss_mib=rss_mib,
    )


# Every case in this module must finish quickly when it passes, ideally in
# under one second, because these tests run with every test run, including on
# slower GitHub Actions runners.
RETAINED_MEMORY_CASES = [
    _single_file_memory_case("large_operation_volume"),
    _single_file_memory_case("destruction_contracts"),
    _single_file_memory_case("many_substantial_actions"),
    _single_file_memory_case("wide_destruction"),
    RetainedMemoryCase(
        name="reference_graph_project",
        source=PurePosixPath("reference_graph_project/test.dfn"),
        filesystem=True,
        rss_mib=192,
    ),
    _single_file_memory_case("particle_operations"),
    _single_file_memory_case("guarantee_expansion"),
    _single_file_memory_case("deep_requirements"),
    _single_file_memory_case("pending_guarantees", rss_mib=384),
]


@dataclasses.dataclass(kw_only=True)
class CpuGrowthCase:
    """A small control program and a larger adversarial variant of it."""

    name: str
    # Both programs are relative to COMPILER_RESOURCES_DIRECTORY.
    control: PurePosixPath
    source: PurePosixPath
    filesystem: bool
    maximum_ratio: float
    # Whether both programs are expected to report diagnostics and fail.
    expect_diagnostics: bool = False


def _non_filesystem_case(
    name: str,
    *,
    control: str,
    source: str,
    maximum_ratio: float,
    expect_diagnostics: bool = False,
) -> CpuGrowthCase:
    return CpuGrowthCase(
        name=name,
        control=PurePosixPath(f"{control}.dfn"),
        source=PurePosixPath(f"{source}.dfn"),
        filesystem=False,
        maximum_ratio=maximum_ratio,
        expect_diagnostics=expect_diagnostics,
    )


CPU_GROWTH_CASES = [
    _non_filesystem_case(
        "pending_guarantees",
        control="pending_guarantees_growth_control",
        source="pending_guarantees_growth",
        maximum_ratio=8,
    ),
    CpuGrowthCase(
        name="reference_depth_updates",
        control=PurePosixPath("reference_depth_updates_control_project/test.dfn"),
        source=PurePosixPath("reference_depth_updates_project/test.dfn"),
        filesystem=True,
        maximum_ratio=2,
    ),
    _non_filesystem_case(
        "shared_quality_implications",
        control="quality_implications_control",
        source="quality_implications",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "deep_quality_implications",
        control="deep_quality_implications_control",
        source="deep_quality_implications",
        maximum_ratio=5,
    ),
    _non_filesystem_case(
        "deep_shared_quality_implications",
        control="deep_shared_quality_implications_control",
        source="deep_shared_quality_implications",
        maximum_ratio=5,
    ),
    _non_filesystem_case(
        "triggered_children_destruction",
        control="triggered_children_destruction_control",
        source="triggered_children_destruction",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_destructors",
        control="triggered_children_destruction_destructors_control",
        source="triggered_children_destruction_destructors",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_contracted",
        control="triggered_children_destruction_contracted_control",
        source="triggered_children_destruction_contracted",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_move",
        control="triggered_children_destruction_move_control",
        source="triggered_children_destruction_move",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_rearrange",
        control="triggered_children_destruction_rearrange_control",
        source="triggered_children_destruction_rearrange",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_rearrange_destructors",
        control="triggered_children_destruction_rearrange_destructors_control",
        source="triggered_children_destruction_rearrange_destructors",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_error",
        control="triggered_children_destruction_error_control",
        source="triggered_children_destruction_error",
        maximum_ratio=4,
        expect_diagnostics=True,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_dependent_siblings",
        control="triggered_children_destruction_dependent_siblings_control",
        source="triggered_children_destruction_dependent_siblings",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_in_destructor",
        control="triggered_children_destruction_in_destructor_control",
        source="triggered_children_destruction_in_destructor",
        maximum_ratio=4,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_in_destructor_contracted",
        control="triggered_children_destruction_in_destructor_contracted_control",
        source="triggered_children_destruction_in_destructor_contracted",
        maximum_ratio=4,
        expect_diagnostics=True,
    ),
    _non_filesystem_case(
        "triggered_children_destruction_same_particle",
        control="triggered_children_destruction_same_particle_control",
        source="triggered_children_destruction_same_particle",
        maximum_ratio=4,
    ),
]
