# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import (
    generated_program_runner,
    test_helpers,
    trace_analysis,
)
from define.compiler.validator.test_helpers import assert_no_errors
from define.runtime import tracing

_TESTDATA_ROOT = Path("define/testdata/tracing/tracing_integration")
_UNSUPPORTED_DESTRUCTOR_CASE_REASONS = {
    "caller_emptied_destructor_position_uses_child_destroy": (
        "codegen cannot lower destructor triggers fired by RequirementNodes"
    ),
    "default_empty_destructor_position_uses_parent_fill": (
        "codegen cannot lower destructor triggers fired by RequirementNodes"
    ),
    "destructor_and_known_children_with_caller_known_occupancy": (
        "codegen cannot lower destructor triggers fired by RequirementNodes"
    ),
    "destructor_known_only_two_callers_up": (
        "destructors learned through Destruction Contracts are not recorded"
    ),
    "destructor_on_particle_from_callee_guarantee": (
        "codegen cannot lower destructor triggers fired by GuaranteeNodes"
    ),
    "destructor_with_children_known_only_two_callers_up": (
        "destructors learned through Destruction Contracts are not recorded"
    ),
}
_GENERATED_TRACE_TEST_CASES = [
    pytest.param(
        test_file.parent,
        id=test_file.parent.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_DESTRUCTOR_CASE_REASONS[test_file.parent.name],
        )
        if test_file.parent.name in _UNSUPPORTED_DESTRUCTOR_CASE_REASONS
        else (),
    )
    for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]
_UNLOWERABLE_DESTRUCTOR_CASES = {
    "caller_emptied_destructor_position_uses_child_destroy",
    "default_empty_destructor_position_uses_parent_fill",
    "destructor_and_known_children_with_caller_known_occupancy",
    "destructor_on_particle_from_callee_guarantee",
    "destructor_with_children_known_only_two_callers_up",
}
_CONCURRENT_RUNTIME_TEST_CASES = [
    pytest.param(
        test_file.parent,
        id=test_file.parent.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_DESTRUCTOR_CASE_REASONS[test_file.parent.name],
        )
        if test_file.parent.name in _UNLOWERABLE_DESTRUCTOR_CASES
        else (),
    )
    for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]


def _compile(generated_dir: Path) -> driver.DriverResult:
    generated_dir.mkdir()
    result = driver.Driver().compile_program(
        Path("test.dfn"),
        generated_dir,
        trace_operations=True,
    )
    assert_no_errors(result.result)
    test_helpers.assert_generated_directory_matches(
        Path("expected_trace"),
        generated_dir,
    )
    return result


def _trace(
    generated_dir: Path,
    trace_file: Path,
    *,
    max_threads: int | None = None,
) -> list[tracing.OperationTraceRecord]:
    runtime_result = generated_program_runner.run_generated_program(
        generated_dir,
        trace_file=trace_file,
        max_threads=max_threads,
    )
    if runtime_result.returncode != 0:
        pytest.fail(runtime_result.stderr)
    return trace_analysis.read_operation_trace(trace_file)


@pytest.mark.parametrize(
    "test_case_dir",
    _GENERATED_TRACE_TEST_CASES,
)
def test_generated_trace_matches_expected_artifacts(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    _ = _compile(generated_dir)
    trace = _trace(
        generated_dir,
        tmp_path / "operation_trace.json",
        # Have to do max_threads=1 to make the operation_trace.json's order deterministic.
        max_threads=1,
    )
    assert trace == trace_analysis.read_operation_trace(Path("operation_trace.json"))


@pytest.mark.parametrize(
    "test_case_dir",
    _CONCURRENT_RUNTIME_TEST_CASES,
)
def test_concurrent_runtime_respects_resolved_operation_dependencies(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    result = _compile(generated_dir)
    trace = _trace(
        generated_dir,
        tmp_path / "operation_trace.json",
    )
    entry_action = result.result.entry_action
    assert entry_action is not None
    for dependency, operation in trace_analysis.resolved_dependency_pairs(
        result.operation_graphs,
        entry_action,
    ):
        assert trace.count(dependency) == 1
        assert trace.count(operation) == 1
        assert trace.index(dependency) < trace.index(operation)
