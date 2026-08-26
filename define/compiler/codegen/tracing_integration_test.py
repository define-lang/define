# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from __future__ import annotations

from pathlib import Path

import pytest

from define.compiler import driver
from define.compiler.codegen import (
    generated_program_runner,
    operation_dependency_analysis,
    test_helpers,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TESTDATA_ROOT = Path("define/testdata/tracing/tracing_integration")
_TRACE_TEST_CASE_DIRS = [
    test_file.parent for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]
_CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED = (
    "caller-added Destructor operation ordering is not generated"
)
_CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED = (
    "a child Destructor known only through the creator is not generated"
)
_UNSUPPORTED_CONCURRENT_RUNTIME_CASE_REASONS = {
    "caller_interleaves_destructors_with_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "creator_reverse_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "destructor_ordering_move_retains_independent_empty_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "diamond_callers_serialize_added_destructor_around_known_destructor": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "two_caller_known_destructors_precede_same_child_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
}
_GENERATED_RUNTIME_OPERATION_DEPENDENCIES_DIFFER = (
    "generated runtime operation dependencies differ from the resolved Operation Graph"
)
_GENERATED_RUNTIME_REPEATS_DIRECT_OPERATION_DEPENDENCIES = (
    "generated runtime repeats a direct Particle Operation dependency"
)
_RUNTIME_CASES_WITH_REPEATED_DIRECT_OPERATION_DEPENDENCIES = {
    "all_positions_five_destroyer_empty_caller_empty",
    "all_positions_five_destroyer_empty_caller_occupied",
    "all_positions_five_destroyer_occupied_caller_empty",
    "all_positions_five_destroyer_occupied_caller_occupied",
    "all_positions_three_destroyer_empty_caller_empty",
    "all_positions_three_destroyer_empty_caller_occupied",
    "all_positions_three_destroyer_occupied_caller_empty",
    "all_positions_three_destroyer_occupied_caller_occupied",
    "auto_destruction_of_child_with_caller_known_destructor",
    "callee_child_state_precedes_destructor_knowledge",
    "caller_contributed_child_destruction_precedes_later_operation",
    "caller_contributed_child_destructor_depends_on_callee_guarantee",
    "caller_contributed_destructor_with_mixed_interface_child_state",
    "caller_emptied_destructor_position_uses_child_destroy",
    "caller_introduces_five_empty_children",
    "caller_introduces_five_empty_children_between_occupied_children",
    "caller_introduces_five_occupied_children",
    "caller_introduces_five_occupied_children_between_empty_children",
    "caller_introduces_three_empty_children",
    "caller_introduces_three_empty_children_between_occupied_children",
    "caller_introduces_three_occupied_children",
    "caller_introduces_three_occupied_children_between_empty_children",
    "caller_known_child_destroy_and_destructor_precede_parent_destroy",
    "caller_known_destructor_precedes_destroyer_known_child_destroy",
    "caller_moves_callee_guaranteed_particle_before_destroying",
    "caller_operation_waits_on_callee_move_output",
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions",
    "creator_reverse_child_order_is_canonical_across_three_actions",
    "deep_diamond_operations_on_the_same_implied_position_with_destructor",
    "default_empty_destructor_position_uses_parent_fill",
    "destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee",
    "destroying_action_reused_with_known_child_empty_then_occupied",
    "destruction_cascade_includes_disjoint_child_paths_from_two_callers",
    "destructor_and_known_children_with_caller_known_occupancy",
    "destructor_and_later_operation",
    "destructor_attached_in_callee_on_implied_position_guarantee",
    "destructor_interface_state_completed_by_creator",
    "destructor_known_only_two_callers_up",
    "destructor_on_child_carried_by_parent_move",
    "destructor_on_implied_position_from_transitive_callee_guarantee",
    "destructor_on_particle_from_callee_guarantee",
    "destructor_on_particle_from_transitive_callee_guarantee",
    "destructor_on_passed_particle_with_newly_known_child",
    "destructor_ordering_action_parent_rule",
    "destructor_reached_through_two_implication_paths",
    "destructor_requirements_resolved_across_three_callers",
    "destructor_with_children_known_only_two_callers_up",
    "destructor_work_runs_concurrently_with_child_cascade",
    "diamond_callers_order_added_destructor_around_known_destructor",
    "direct_and_implied_destructor_executes_once",
    "direct_destructor_with_mixed_interface_child_state",
    "intermediate_callee_operation_suppresses_only_its_caller_path",
    "multiple_constructors_and_destructors_modify_same_implied_position",
    "multiple_constructors_run_in_parallel_with_destroy_and_destructors",
    "multiple_destructors_all_fire_on_destroy",
    "multiple_destructors_on_particle_from_callee_guarantee",
    "multiple_newly_known_children_with_destructors",
    "nested_caller_contributed_destructor",
    "nested_repeated_destructor_with_caller_known_child",
    "newly_known_grandchild_destructor_uses_callee_child_destroy",
    "only_relevant_retrigger_receives_forwarded_destruction_connections",
    "repeated_destroyer_executions_receive_own_destructors",
    "repeated_destructor_uses_distinct_requirement_sources",
    "repeated_executions_each_destroy_two_particles",
    "reused_callee_receives_distinct_destruction_connections_per_execution",
    "separate_child_contract_paths",
    "two_caller_known_destructors_precede_same_child_destroy",
    "two_destruction_facts_with_distinct_destructor_sets",
}
_RUNTIME_OPERATION_DEPENDENCY_RELATION_MISMATCH_CASES = {
    "actions_with_identically_named_child_actions_have_distinct_instances",
    "callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy",
    "callee_child_state_precedes_destructor_knowledge",
    "caller_added_destructor_fans_out_from_action_parent",
    "caller_added_destructor_fires_in_callee",
    "caller_added_destructor_with_later_action_execution",
    "caller_added_multiple_destructors_fire_in_callee",
    "caller_contributed_child_destructor_depends_on_callee_guarantee",
    "caller_contributed_destructor_with_mixed_interface_child_state",
    "caller_destructor_between_two_destroyer_known_destructors",
    "caller_emptied_destructor_position_uses_child_destroy",
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
    "caller_known_destructor_precedes_destroyer_known_child_destroy",
    "caller_moves_callee_guaranteed_particle_before_destroying",
    "contributed_destructor_depends_on_callee_move_with_two_dependencies",
    "contributed_destructor_operates_on_child_of_occupied_requirement",
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions",
    "creator_reverse_child_order_is_canonical_across_three_actions",
    "deep_diamond_operations_on_the_same_implied_position",
    "deep_diamond_operations_on_the_same_implied_position_with_destructor",
    "default_empty_destructor_position_uses_parent_fill",
    "destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee",
    "destruction_cascade_includes_disjoint_child_paths_from_two_callers",
    "destructor_attached_in_callee_on_implied_position_guarantee",
    "destructor_on_implied_position_from_transitive_callee_guarantee",
    "destructor_on_particle_from_callee_guarantee",
    "destructor_on_particle_from_transitive_callee_guarantee",
    "destructor_ordering_action_parent_rule",
    "destructor_ordering_fill_rule",
    "destructor_ordering_move_retains_independent_empty_dependency",
    "destructor_ordering_move_retains_independent_fill_dependency",
    "destructor_requirements_resolved_across_three_callers",
    "diamond_callers_order_added_destructor_around_known_destructor",
    "diamond_callers_serialize_added_destructor_around_known_destructor",
    "intermediate_callee_operation_suppresses_only_its_caller_path",
    "local_create_and_action_execution_run_in_parallel",
    "multiple_destructors_on_particle_from_callee_guarantee",
    "only_relevant_retrigger_receives_forwarded_destruction_connections",
    "repeated_executions_each_destroy_two_particles",
    "repeated_triggerings",
    "two_actions_each_triggering_one_action_twice_number_its_invocations_across_the_program",
    "two_caller_known_destructors_precede_same_child_destroy",
    "two_destruction_facts_with_distinct_destructor_sets",
}
_RUNTIME_SCHEDULING_TABLE_MISMATCH_CASES = (
    _RUNTIME_OPERATION_DEPENDENCY_RELATION_MISMATCH_CASES
    | _RUNTIME_CASES_WITH_REPEATED_DIRECT_OPERATION_DEPENDENCIES
    | {"destructor_fragments_finish_before_cascade_frees_positions"}
)


def _concurrent_runtime_test_case(test_case_dir: Path):
    if test_case_dir.name in _UNSUPPORTED_CONCURRENT_RUNTIME_CASE_REASONS:
        return pytest.param(
            test_case_dir,
            id=test_case_dir.name,
            marks=pytest.mark.xfail(
                strict=False,
                reason=_UNSUPPORTED_CONCURRENT_RUNTIME_CASE_REASONS[test_case_dir.name],
            ),
        )
    if test_case_dir.name in _RUNTIME_OPERATION_DEPENDENCY_RELATION_MISMATCH_CASES:
        return pytest.param(
            test_case_dir,
            id=test_case_dir.name,
            marks=pytest.mark.xfail(
                strict=True,
                reason=_GENERATED_RUNTIME_OPERATION_DEPENDENCIES_DIFFER,
            ),
        )
    return pytest.param(test_case_dir, id=test_case_dir.name)


_CONCURRENT_RUNTIME_TEST_CASES = [
    _concurrent_runtime_test_case(test_case_dir)
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]


def _runtime_operation_dependency_test_case(test_case_dir: Path):
    if test_case_dir.name not in _RUNTIME_SCHEDULING_TABLE_MISMATCH_CASES:
        return pytest.param(test_case_dir, id=test_case_dir.name)
    return pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_GENERATED_RUNTIME_OPERATION_DEPENDENCIES_DIFFER,
        ),
    )


_RUNTIME_OPERATION_DEPENDENCY_TEST_CASES = [
    _runtime_operation_dependency_test_case(test_case_dir)
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]


def _direct_operation_dependency_uniqueness_test_case(test_case_dir: Path):
    if (
        test_case_dir.name
        not in _RUNTIME_CASES_WITH_REPEATED_DIRECT_OPERATION_DEPENDENCIES
    ):
        return pytest.param(test_case_dir, id=test_case_dir.name)
    return pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_GENERATED_RUNTIME_REPEATS_DIRECT_OPERATION_DEPENDENCIES,
        ),
    )


_DIRECT_OPERATION_DEPENDENCY_UNIQUENESS_TEST_CASES = [
    _direct_operation_dependency_uniqueness_test_case(test_case_dir)
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]


def _compile(generated_dir: Path) -> driver.CompilationResult:
    generated_dir.mkdir()
    result = driver.Driver().compile_program(
        Path("test.dfn"),
        generated_dir,
        trace_operations=True,
    )
    assert_no_errors(result)
    return result


def _runtime_operation_dependencies(
    generated_dir: Path,
    dependencies_file: Path,
    *,
    max_threads: int | None = None,
) -> operation_dependency_analysis.OperationDependencies:
    runtime_result = generated_program_runner.run_generated_program(
        generated_dir,
        operation_dependencies_file=dependencies_file,
        max_threads=max_threads,
    )
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)
    return operation_dependency_analysis.read_operation_dependencies(dependencies_file)


def _resolved_operation_dependencies(
    result: driver.CompilationResult,
) -> operation_dependency_analysis.OperationDependencies:
    entry_action = result.entry_action
    assert entry_action is not None
    return operation_dependency_analysis.resolved_operation_dependencies(
        result.operation_graphs,
        entry_action,
    )


@pytest.mark.parametrize(
    "test_case_dir",
    _TRACE_TEST_CASE_DIRS,
)
def test_generated_tracing_code_matches_expected_artifacts(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Each Define case generates its expected Python program with Particle Operation tracing enabled."""
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    _ = _compile(generated_dir)
    test_helpers.assert_generated_directory_matches(
        Path("expected_trace"),
        generated_dir,
    )


@pytest.mark.parametrize(
    "test_case_dir",
    _DIRECT_OPERATION_DEPENDENCY_UNIQUENESS_TEST_CASES,
)
def test_runtime_direct_operation_dependencies_are_unique(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Each Particle Operation records each direct operation dependency only once at runtime."""
    if (
        test_case_dir.name
        == "diamond_callers_serialize_added_destructor_around_known_destructor"
    ):
        pytest.xfail(_CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED)
    monkeypatch.chdir(test_case_dir.resolve())
    operation_dependencies = _runtime_operation_dependencies(
        Path("expected_trace"),
        tmp_path / "operation_dependencies.json",
        max_threads=1,
    )
    for direct_dependencies in operation_dependencies.values():
        assert direct_dependencies == tuple(dict.fromkeys(direct_dependencies))


@pytest.mark.parametrize(
    "test_case_dir",
    _CONCURRENT_RUNTIME_TEST_CASES,
)
def test_concurrent_runtime_dependency_relationships_match_resolved_operation_graph(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Concurrent programs realize exactly the dependency relationships required by their full-program Operation Graph."""
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    result = _compile(generated_dir)
    runtime_dependencies = _runtime_operation_dependencies(
        generated_dir,
        tmp_path / "operation_dependencies.json",
    )
    resolved_dependencies = _resolved_operation_dependencies(result)
    assert runtime_dependencies.keys() == resolved_dependencies.keys()
    assert (
        runtime_dependencies.transitive_dependency_pairs()
        == resolved_dependencies.transitive_dependency_pairs()
    )


@pytest.mark.parametrize(
    "test_case_dir",
    _RUNTIME_OPERATION_DEPENDENCY_TEST_CASES,
)
def test_generated_runtime_operation_dependencies_match_resolved_operation_graph(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """With one worker, each case realizes its expected Particle Operation order and exact direct dependencies."""
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    result = _compile(generated_dir)
    runtime_dependencies_file = tmp_path / "operation_dependencies.json"
    runtime_dependencies = _runtime_operation_dependencies(
        generated_dir,
        runtime_dependencies_file,
        max_threads=1,
    )
    assert (
        runtime_dependencies_file.read_bytes()
        == Path("operation_dependencies.json").read_bytes()
    )
    resolved_dependencies = _resolved_operation_dependencies(result)
    assert (
        runtime_dependencies.as_scheduling_table()
        == resolved_dependencies.as_scheduling_table()
    )
