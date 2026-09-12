# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from __future__ import annotations

from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import generated_program_runner, test_helpers
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/tracing/tracing_integration")
_TEST_CASE_DIRS = [
    test_file.parent for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]
_DESTRUCTION_CONTRACT_TRACE_MISMATCH_CASES = {
    "callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy",
    "caller_destructor_between_two_destroyer_known_destructors",
    "caller_interleaves_destructors_with_destroyer_known_destructors",
    "caller_introduces_five_empty_children",
    "caller_introduces_five_empty_children_between_occupied_children",
    "caller_introduces_five_occupied_children",
    "caller_introduces_five_occupied_children_between_empty_children",
    "caller_introduces_three_empty_children",
    "caller_introduces_three_empty_children_between_occupied_children",
    "caller_introduces_three_occupied_children",
    "caller_introduces_three_occupied_children_between_empty_children",
    "caller_known_child_destroy_and_destructor_precede_parent_destroy",
    "contributed_destructor_depends_on_callee_move_with_two_dependencies",
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions",
    "creator_reverse_child_order_is_canonical_across_three_actions",
    "destructor_ordering_action_parent_rule",
    "destructor_ordering_fill_rule",
    "destructor_ordering_move_retains_independent_empty_dependency",
    "destructor_ordering_move_retains_independent_fill_dependency",
    "diamond_callers_serialize_added_destructor_around_known_destructor",
    "two_caller_known_destructors_precede_same_child_destroy",
}
_DESTRUCTION_CONTRACT_TRACE_MISMATCH = (
    "generated execution does not realize the intended Destruction Contract "
    "operation sequence"
)
_RUNTIME_TEST_CASES: list[object] = []
for test_case_dir in _TEST_CASE_DIRS:
    marks = ()
    if test_case_dir.name in _DESTRUCTION_CONTRACT_TRACE_MISMATCH_CASES:
        marks = pytest.mark.xfail(
            strict=True,
            reason=_DESTRUCTION_CONTRACT_TRACE_MISMATCH,
        )
    _RUNTIME_TEST_CASES.append(
        pytest.param(test_case_dir, id=test_case_dir.name, marks=marks)
    )


def _compile(generated_dir: Path):
    generated_dir.mkdir()
    result = driver.Driver().compile_program(
        Path("test.dfn"),
        generated_dir,
        trace_operations=True,
    )
    assert_no_errors(result)


def _test_id(test_case_dir: Path) -> str:
    return test_case_dir.name


@pytest.mark.parametrize("test_case_dir", _TEST_CASE_DIRS, ids=_test_id)
def test_generated_tracing_code_matches_expected_artifacts(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    _compile(generated_dir)
    test_helpers.assert_generated_directory_matches(
        Path("expected_trace"), generated_dir
    )


@pytest.mark.parametrize("test_case_dir", _RUNTIME_TEST_CASES)
def test_runtime_operation_order_matches_expected_trace(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    trace_file = tmp_path / "operation_trace.txt"
    runtime_result = generated_program_runner.run_generated_program(
        Path("expected_trace"),
        operation_trace_file=trace_file,
        max_threads=1,
    )
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)
    assert trace_file.read_bytes() == Path("operation_trace.txt").read_bytes()
