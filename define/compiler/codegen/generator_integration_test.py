# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each test case is a category/case directory under the shared codegen testdata
tree containing a test.dfn entry point, an expected/ directory with the expected
generated files, and an occupied_positions.txt runtime expectation.
"""

import difflib
import glob
import tempfile
from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/codegen")
_TEST_CASES = sorted(
    Path(path).parent for path in glob.glob(str(_TESTDATA_ROOT / "*/*/test.dfn"))
)


def _all_files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _assert_dirs_equal(expected: Path, generated: Path):
    """Assert two directory trees are identical."""
    expected_files = _all_files(expected)
    generated_files = _all_files(generated)
    if expected_files == generated_files:
        return
    diffs: list[str] = []
    all_keys = sorted(set(expected_files) | set(generated_files))
    for key in all_keys:
        exp = expected_files.get(key, "")
        gen = generated_files.get(key, "")
        if exp != gen:
            diffs.extend(
                difflib.unified_diff(
                    exp.splitlines(keepends=True),
                    gen.splitlines(keepends=True),
                    fromfile=f"expected/{key}",
                    tofile=f"generated/{key}",
                )
            )
    pytest.fail("".join(diffs))


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
    _assert_dirs_equal(expected_dir, output_dir)


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASES,
    ids=[path.relative_to(_TESTDATA_ROOT).as_posix() for path in _TEST_CASES],
)
def test_expected_output_runs(test_case_dir: Path):
    expected_dir = test_case_dir / "expected"
    result = generated_program_runner.run_generated_program(expected_dir)
    if result.returncode != 0:
        pytest.fail(result.stderr)

    occupied_file = test_case_dir / "occupied_positions.txt"
    expected_occupied = occupied_file.read_text()
    if result.stdout != expected_occupied:
        diff = difflib.unified_diff(
            expected_occupied.splitlines(keepends=True),
            result.stdout.splitlines(keepends=True),
            fromfile="expected occupied_positions.txt",
            tofile="actual program output",
        )
        pytest.fail("".join(diff))
