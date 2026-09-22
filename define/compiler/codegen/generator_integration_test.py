# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each test case is a category/case directory under the shared codegen testdata
tree containing a test.dfn entry point, an expected/ directory with the expected
generated files.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

_TEST_CASES = test_helpers.codegen_test_cases()


def test_test_cases_not_empty():
    assert _TEST_CASES


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=test_helpers.codegen_test_case_id,
)
def test_generates_expected_output(
    test_case_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    expected_dir = (test_case_dir / "expected").resolve()

    monkeypatch.chdir(test_case_dir)
    output_dir = Path(tempfile.mkdtemp())
    result = driver.Driver().compile_program(Path("test.dfn"), output_dir)

    assert_no_errors(result)
    test_helpers.assert_generated_directory_matches(expected_dir, output_dir)


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
