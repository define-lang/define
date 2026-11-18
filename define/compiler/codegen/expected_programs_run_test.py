"""Tests that each codegen case's expected generated programs run."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.codegen import generated_program_runner, test_helpers

if TYPE_CHECKING:
    from pathlib import Path

_TEST_CASES = test_helpers.codegen_test_cases()


def test_test_cases_not_empty():
    assert _TEST_CASES


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=test_helpers.codegen_test_case_id,
)
def test_expected_output_runs(test_case_dir: Path):
    expected_dir = test_case_dir / "expected"
    result = generated_program_runner.run_generated_program(expected_dir)
    if result.returncode != 0:
        pytest.fail(result.stderr)


@pytest.mark.parametrize(
    "test_case_dir", _TEST_CASES, ids=test_helpers.codegen_test_case_id
)
def test_runtime_operation_order_matches_expected_trace(
    test_case_dir: Path,
    tmp_path: Path,
):
    trace_file = tmp_path / "operation_trace.txt"
    runtime_result = generated_program_runner.run_generated_program(
        test_case_dir / "expected_trace",
        environment={"DEFINE_OPERATION_TRACE_FILE": str(trace_file)},
    )
    if runtime_result.returncode != 0:
        pytest.fail(runtime_result.stderr)
    assert (
        trace_file.read_bytes() == (test_case_dir / "operation_trace.txt").read_bytes()
    )
