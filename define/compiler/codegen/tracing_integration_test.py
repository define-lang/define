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
# TODO: Remove these xfails when serial Destruction Contracts are generated.
_DESTRUCTION_CONTRACT_CASES = {
    "all_positions_five_destroyer_empty_caller_occupied",
    "all_positions_five_destroyer_occupied_caller_occupied",
    "all_positions_three_destroyer_empty_caller_occupied",
    "all_positions_three_destroyer_occupied_caller_occupied",
    "auto_destruction_of_child_with_caller_known_destructor",
    "callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy",
    "callee_child_state_precedes_destructor_knowledge",
    "callee_move_waits_on_two_caller_child_operations_and_one_intermediate_child_operation",
    "caller_added_destructor_discovers_callees_and_their_destructors",
    "caller_added_destructor_fans_out_from_action_parent",
    "caller_added_destructor_fires_in_callee",
    "caller_added_destructor_with_later_action_execution",
    "caller_added_multiple_destructors_fire_in_callee",
    "caller_configures_destructor_from_callee_guarantee",
    "caller_configures_multiple_destroys_after_separate_binding_inits",
    "caller_contributed_child_destruction_precedes_later_operation",
    "caller_contributed_child_destructor_depends_on_callee_guarantee",
    "caller_contributed_destruction_follows_transitive_move_guarantee",
    "caller_contributed_destructor_with_mixed_implied_position_state",
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
    "caller_known_child_destroy_is_independent_of_callee_sibling_moves",
    "caller_known_child_destroy_uses_binding_initialized_callee_fanout",
    "caller_known_child_has_same_destructor_as_callee_known_parent",
    "caller_known_destructor_precedes_destroyer_known_child_destroy",
    "contributed_destructor_calls_action_with_child_destruction",
    "contributed_destructor_depends_on_callee_move_with_two_dependencies",
    "contributed_destructor_operates_on_child_of_occupied_requirement",
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions",
    "creator_reverse_child_order_is_canonical_across_three_actions",
    "destroying_action_reused_with_known_child_empty_then_occupied",
    "destruction_cascade_includes_disjoint_child_paths_from_two_callers",
    "destructor_implied_position_state_completed_by_creator",
    "destructor_on_passed_particle_with_newly_known_child",
    "destructor_ordering_action_parent_rule",
    "destructor_ordering_fill_rule",
    "destructor_ordering_move_retains_independent_empty_dependency",
    "destructor_ordering_move_retains_independent_fill_dependency",
    "destructor_reached_through_two_implication_paths",
    "destructor_requirements_resolved_across_three_callers",
    "destructor_with_children_known_only_two_callers_up",
    "diamond_callers_order_added_destructor_around_known_destructor",
    "diamond_callers_serialize_added_destructor_around_known_destructor",
    "direct_and_implied_destructor_executes_once",
    "direct_destructor_with_mixed_implied_position_state",
    "intermediate_callee_operation_suppresses_only_its_caller_path",
    "later_caller_adds_destructor_to_contributed_child_destroy",
    "later_caller_adds_independent_destructor_to_contributed_child_destroy",
    "multiple_newly_known_children_with_destructors",
    "nested_caller_contributed_destructor",
    "nested_repeated_destructor_with_caller_known_child",
    "newly_known_grandchild_destructor_uses_callee_child_destroy",
    "only_relevant_retrigger_receives_forwarded_destruction_connections",
    "propagated_empty_rule_combines_caller_operation_and_callee_guarantee",
    "repeated_destroyer_executions_receive_own_destructors",
    "repeated_destructor_uses_distinct_requirement_sources",
    "repeated_executions_each_destroy_two_particles",
    "reused_callee_receives_distinct_destruction_connections_per_execution",
    "separate_child_contract_paths",
    "two_caller_known_destructors_precede_same_child_destroy",
    "two_destruction_facts_with_distinct_destructor_sets",
}
_RUNTIME_TEST_CASES: list[object] = []
for test_case_dir in _TEST_CASE_DIRS:
    marks = ()
    if test_case_dir.name in _DESTRUCTION_CONTRACT_CASES:
        marks = pytest.mark.xfail(
            strict=True,
            reason="serial Destruction Contracts are not generated yet",
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
    )
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)
    assert trace_file.read_bytes() == Path("operation_trace.txt").read_bytes()
