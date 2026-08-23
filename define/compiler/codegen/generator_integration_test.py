# pyright: reportUnusedCallResult=false
"""Integration tests for code generation.

Each test case is a category/case directory under the shared codegen testdata
tree containing a test.dfn entry point, an expected/ directory with the expected
generated files, and an occupied_positions.txt runtime expectation.
"""

from __future__ import annotations

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
_CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED = (
    "caller-added Destructor operation ordering is not generated"
)
_UNSUPPORTED_TEST_CASE_REASONS = {
    "operation_graph_destructor_integration/callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_destructor_between_two_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_interleaves_destructors_with_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/contributed_destructor_depends_on_callee_move_with_two_dependencies": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_action_parent_rule": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_fill_rule": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_move_retains_independent_empty_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_move_retains_independent_fill_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
}
_TEST_CASE_PARAMS: list[object] = []
for test_case_dir in _TEST_CASES:
    test_case_id = test_case_dir.relative_to(_TESTDATA_ROOT).as_posix()
    marks = ()
    if test_case_id in _UNSUPPORTED_TEST_CASE_REASONS:
        marks = pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_TEST_CASE_REASONS[test_case_id],
        )
    _TEST_CASE_PARAMS.append(
        pytest.param(
            test_case_dir,
            id=test_case_id,
            marks=marks,
        )
    )


def test_test_cases_not_empty():
    assert _TEST_CASES


@pytest.mark.parametrize(
    "test_case_dir",
    _TEST_CASE_PARAMS,
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
    _TEST_CASE_PARAMS,
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
