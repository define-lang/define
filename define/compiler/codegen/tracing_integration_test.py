# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.codegen import (
    generated_program_runner,
    test_helpers,
    testdata_cases,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from pathlib import Path

_TEST_CASE_DIRS = test_helpers.codegen_test_cases()


def _compile(case_dir: Path, generated_dir: Path):
    generated_dir.mkdir()
    result = testdata_cases.compile_case(case_dir, generated_dir, trace_operations=True)
    assert_no_errors(result)


def test_test_cases_not_empty():
    assert _TEST_CASE_DIRS


@pytest.mark.parametrize(
    "test_case_dir", _TEST_CASE_DIRS, ids=test_helpers.codegen_test_case_id
)
def test_generated_tracing_code_matches_expected_artifacts(
    test_case_dir: Path,
    tmp_path: Path,
    request: pytest.FixtureRequest,
):
    test_helpers.mark_nondeterministic_definition_order(request, test_case_dir)
    generated_dir = tmp_path / "generated"
    _compile(test_case_dir, generated_dir)
    test_helpers.assert_generated_directory_matches(
        test_case_dir / "expected_trace", generated_dir
    )


@pytest.mark.parametrize(
    "test_case_dir", _TEST_CASE_DIRS, ids=test_helpers.codegen_test_case_id
)
def test_runtime_operation_order_matches_expected_trace(
    test_case_dir: Path,
    tmp_path: Path,
):
    trace_file = tmp_path / "operation_trace.txt"
    runtime_result = generated_program_runner.run_generated_program(
        test_case_dir / "expected_trace",
        operation_trace_file=trace_file,
    )
    if runtime_result.returncode != 0:
        pytest.fail(runtime_result.stderr)
    assert (
        trace_file.read_bytes() == (test_case_dir / "operation_trace.txt").read_bytes()
    )
