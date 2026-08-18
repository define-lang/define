# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

import collections
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
_TRACE_TEST_CASE_DIRS = [
    test_file.parent for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]
_UNSUPPORTED_TRACE_CASE_REASONS = {
    "destructor_known_only_two_callers_up": (
        "destructors learned through Destruction Contracts are not recorded"
    ),
    "destructor_with_children_known_only_two_callers_up": (
        "destructors learned through Destruction Contracts are not recorded"
    ),
}
_GENERATED_TRACE_TEST_CASES = [
    pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_TRACE_CASE_REASONS[test_case_dir.name],
        )
        if test_case_dir.name in _UNSUPPORTED_TRACE_CASE_REASONS
        else (),
    )
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]
_GENERATED_OPERATION_TRACE_TEST_CASES = [
    pytest.param(
        trace_file.parent,
        id=trace_file.parent.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_TRACE_CASE_REASONS[trace_file.parent.name],
        )
        if trace_file.parent.name in _UNSUPPORTED_TRACE_CASE_REASONS
        else (),
    )
    for trace_file in sorted(_TESTDATA_ROOT.glob("*/operation_trace.json"))
]
_CONCURRENT_RUNTIME_TEST_CASES = [
    pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_TRACE_CASE_REASONS[test_case_dir.name],
        )
        if test_case_dir.name in _UNSUPPORTED_TRACE_CASE_REASONS
        else (),
    )
    for test_case_dir in _TRACE_TEST_CASE_DIRS
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
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)
    return trace_analysis.read_operation_trace(trace_file)


def _assert_trace_respects_resolved_operation_dependencies(
    trace: list[tracing.OperationTraceRecord],
    result: driver.DriverResult,
):
    # TODO: Derive the generated runtime's operation partial order independently
    # from the Action Plan, including Action Fragment joins, Binding Hole Fanouts,
    # Callee Binding Joins, guarantees, and destruction connections. Project its
    # synchronization events to Position Operations and compare its transitive
    # closure with the Operation Graph
    # Resolver's closure. Checking one observed trace only proves that execution
    # respected the resolver; it cannot detect extra serialization, and scheduling
    # can conceal a missing generated dependency.
    entry_action = result.result.entry_action
    assert entry_action is not None
    resolved_dependencies = trace_analysis.resolved_operation_dependencies(
        result.operation_graphs,
        entry_action,
    )
    assert collections.Counter(trace) == collections.Counter(
        resolved_dependencies.keys()
    )
    trace_order = {record: index for index, record in enumerate(trace)}
    for operation, dependencies in resolved_dependencies.items():
        for dependency in dependencies:
            assert trace_order[dependency] < trace_order[operation]


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


@pytest.mark.parametrize("test_case_dir", _GENERATED_OPERATION_TRACE_TEST_CASES)
def test_generated_operation_trace_matches_operation_graph_renderer_ordering(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(test_case_dir.resolve())
    result = driver.Driver().validate_program(Path("test.dfn"))
    assert_no_errors(result.result)
    trace = trace_analysis.read_operation_trace(Path("operation_trace.json"))
    _assert_trace_respects_resolved_operation_dependencies(trace, result)


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
    assert collections.Counter(trace) == collections.Counter(
        trace_analysis.read_operation_trace(Path("operation_trace.json"))
    )
    _assert_trace_respects_resolved_operation_dependencies(trace, result)
