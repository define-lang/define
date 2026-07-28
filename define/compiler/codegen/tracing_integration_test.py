# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

import os
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


def _compile_and_trace(
    generated_dir: os.PathLike[str],
    trace_file: os.PathLike[str],
) -> tuple[driver.DriverResult, list[tracing.OperationTraceRecord]]:
    generated_path = Path(generated_dir)
    trace_path = Path(trace_file)
    generated_path.mkdir()
    result = driver.Driver().compile_program(
        Path("test.dfn"),
        generated_path,
        trace_operations=True,
    )
    assert_no_errors(result.result)
    test_helpers.assert_generated_directory_matches(
        Path("expected_trace"),
        generated_path,
    )
    runtime_result = generated_program_runner.run_generated_program(
        generated_path,
        trace_file=trace_path,
    )
    if runtime_result.returncode != 0:
        pytest.fail(runtime_result.stderr)
    trace = trace_analysis.read_operation_trace(trace_path)
    assert trace == trace_analysis.read_operation_trace(Path("operation_trace.json"))
    return result, trace


@pytest.mark.parametrize(
    "test_case_dir",
    [
        pytest.param(test_file.parent, id=test_file.parent.name)
        for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
    ],
)
def test_runtime_respects_resolved_operation_dependencies(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    result, trace = _compile_and_trace(
        tmp_path / "generated",
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
