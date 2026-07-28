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
_TEST_CASES = [
    pytest.param(test_file.parent, id=test_file.parent.name)
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
    _TEST_CASES,
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
    _TEST_CASES,
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
