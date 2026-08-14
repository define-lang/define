# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each test case is a category/case directory under the shared codegen testdata
tree containing a test.dfn entry point, an expected/ directory with the expected
generated files, and an occupied_positions.txt runtime expectation.
"""

import difflib
import glob
import os
import tempfile
from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/codegen")
# Bazel shards these tests by category through this environment variable, but
# direct pytest runners such as mutmut do not set it and must discover all cases.
_TESTDATA_CATEGORY = os.environ.get("DEFINE_CODEGEN_TESTDATA_CATEGORY")
_TESTDATA_PATTERN = (
    f"{_TESTDATA_CATEGORY}/*/test.dfn"
    if _TESTDATA_CATEGORY is not None
    else "*/*/test.dfn"
)
_TEST_CASES = sorted(
    Path(path).parent for path in glob.glob(str(_TESTDATA_ROOT / _TESTDATA_PATTERN))
)


def test_test_cases_not_empty():
    assert _TEST_CASES


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=[path.relative_to(_TESTDATA_ROOT).as_posix() for path in _TEST_CASES],
)
def test_generates_expected_output(
    test_case_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    expected_dir = (test_case_dir / "expected").resolve()

    monkeypatch.chdir(test_case_dir)
    output_dir = Path(tempfile.mkdtemp())
    result = driver.Driver().compile_program(Path("test.dfn"), output_dir)

    assert_no_errors(result.result)
    test_helpers.assert_generated_directory_matches(expected_dir, output_dir)


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=[path.relative_to(_TESTDATA_ROOT).as_posix() for path in _TEST_CASES],
)
def test_expected_output_runs(test_case_dir: Path):
    expected_dir = test_case_dir / "expected"
    result = generated_program_runner.run_generated_program(expected_dir)
    if result.process.returncode != 0:
        pytest.fail(result.process.stderr)

    occupied_file = test_case_dir / "occupied_positions.txt"
    expected_occupied = occupied_file.read_text()
    if result.occupied_positions != expected_occupied:
        diff = difflib.unified_diff(
            expected_occupied.splitlines(keepends=True),
            result.occupied_positions.splitlines(keepends=True),
            fromfile="expected occupied_positions.txt",
            tofile="actual program output",
        )
        pytest.fail("".join(diff))
