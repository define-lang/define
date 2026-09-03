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
_CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED = (
    "a child Destructor known only through the creator is not generated"
)
_CALLEE_CHILD_DESTROY_DEPENDENCY_NOT_GENERATED = (
    "a caller Destroy can race with a callee Destroy on a child position after "
    "the callee moves the parent particle"
)
_DESTRUCTION_CASCADE_NOT_GENERATED = (
    "generated destruction cascade ordering differs from the Operation Graph"
)
_UNSUPPORTED_RUNTIME_TEST_CASE_REASONS = {
    "operation_graph_many_actions_integration/caller_consumes_a_child_guarantee_after_two_action_parent_moves": _CALLEE_CHILD_DESTROY_DEPENDENCY_NOT_GENERATED,
    "operation_graph_many_actions_integration/child_guarantee_with_distinct_occupied_action_parent_and_empty_rule_binding_holes": _CALLEE_CHILD_DESTROY_DEPENDENCY_NOT_GENERATED,
    "operation_graph_many_actions_integration/empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_implied_position_child": _CALLEE_CHILD_DESTROY_DEPENDENCY_NOT_GENERATED,
    "operation_graph_many_actions_integration/input_carried_through_two_moves_reaches_the_triggered_inner": _CALLEE_CHILD_DESTROY_DEPENDENCY_NOT_GENERATED,
    "operation_graph_destructor_integration/callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_destructor_between_two_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_interleaves_destructors_with_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_known_child_destroy_and_destructor_precede_parent_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_five_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_five_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_five_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_five_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_three_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_three_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_three_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/caller_introduces_three_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/creator_nonoverlapping_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "operation_graph_destructor_integration/creator_reverse_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "operation_graph_destructor_integration/contributed_destructor_depends_on_callee_move_with_two_dependencies": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_action_parent_rule": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_fill_rule": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_move_retains_independent_empty_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/destructor_ordering_move_retains_independent_fill_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/diamond_callers_serialize_added_destructor_around_known_destructor": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "operation_graph_destructor_integration/separate_child_contract_paths": _DESTRUCTION_CASCADE_NOT_GENERATED,
    "operation_graph_destructor_integration/two_caller_known_destructors_precede_same_child_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
}
_GENERATION_TEST_CASE_PARAMS: list[object] = []
_RUNTIME_TEST_CASE_PARAMS: list[object] = []
for test_case_dir in _TEST_CASES:
    test_case_id = test_case_dir.relative_to(_TESTDATA_ROOT).as_posix()
    _GENERATION_TEST_CASE_PARAMS.append(
        pytest.param(
            test_case_dir,
            id=test_case_id,
        )
    )
    marks = ()
    if test_case_id in _UNSUPPORTED_RUNTIME_TEST_CASE_REASONS:
        marks = pytest.mark.xfail(
            strict=False,
            reason=_UNSUPPORTED_RUNTIME_TEST_CASE_REASONS[test_case_id],
        )
    _RUNTIME_TEST_CASE_PARAMS.append(
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
    _GENERATION_TEST_CASE_PARAMS,
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
    _RUNTIME_TEST_CASE_PARAMS,
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
