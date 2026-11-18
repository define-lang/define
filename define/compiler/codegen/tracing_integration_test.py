# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.codegen import test_helpers, testdata_cases
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
):
    generated_dir = tmp_path / "generated"
    _compile(test_case_dir, generated_dir)
    test_helpers.assert_generated_directory_matches(
        test_case_dir / "expected_trace", generated_dir
    )
