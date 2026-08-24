# pyright: reportUnusedCallResult=false
"""Integration tests for operation tracing in generated programs."""

from __future__ import annotations

import collections
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from define.compiler import driver
from define.compiler.codegen import (
    generated_program_runner,
    test_helpers,
    trace_analysis,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.runtime import tracing

_TESTDATA_ROOT = Path("define/testdata/tracing/tracing_integration")
_TRACE_TEST_CASE_DIRS = [
    test_file.parent for test_file in sorted(_TESTDATA_ROOT.glob("*/test.dfn"))
]
_CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED = (
    "caller-added Destructor operation ordering is not generated"
)
_DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED = (
    "destructors learned through Destruction Contracts are not recorded"
)
_CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED = (
    "a child Destructor known only through the creator is not generated"
)
_UNSUPPORTED_GENERATED_TRACE_CASE_REASONS = {
    "callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_destructor_between_two_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_interleaves_destructors_with_destroyer_known_destructors": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_five_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_empty_children_between_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_occupied_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_introduces_three_occupied_children_between_empty_children": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "caller_known_child_destroy_and_destructor_precede_parent_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "creator_reverse_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "destructor_interface_state_completed_by_creator": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_requirements_resolved_across_three_callers": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "diamond_callers_serialize_added_destructor_around_known_destructor": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "destructor_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_with_children_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "separate_child_contract_paths": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
}
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
    "destructor_interface_state_completed_by_creator": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_requirements_resolved_across_three_callers": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_ordering_move_retains_independent_empty_dependency": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "diamond_callers_serialize_added_destructor_around_known_destructor": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
    "destructor_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_with_children_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "two_caller_known_destructors_precede_same_child_destroy": _CALLER_ADDED_DESTRUCTOR_ORDERING_NOT_GENERATED,
}
_CONCURRENT_RUNTIME_CASES_WITH_NONDETERMINISTIC_FAILURE = {
    "caller_interleaves_destructors_with_destroyer_known_destructors",
    "caller_introduces_five_empty_children",
    "caller_introduces_five_empty_children_between_occupied_children",
    "caller_introduces_five_occupied_children",
    "caller_introduces_five_occupied_children_between_empty_children",
    "caller_introduces_three_empty_children",
    "caller_introduces_three_empty_children_between_occupied_children",
    "caller_introduces_three_occupied_children",
    "caller_introduces_three_occupied_children_between_empty_children",
    "destructor_ordering_move_retains_independent_empty_dependency",
    "diamond_callers_serialize_added_destructor_around_known_destructor",
    "two_caller_known_destructors_precede_same_child_destroy",
}
_GENERATED_RUNTIME_OPERATION_DEPENDENCIES_DIFFER = (
    "generated runtime operation dependencies differ from the resolved Operation Graph"
)
_RUNTIME_OPERATION_DEPENDENCY_MISMATCH_CASES = {
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
_UNSUPPORTED_OPERATION_TRACE_CASE_REASONS = {
    "creator_nonoverlapping_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "creator_reverse_child_order_is_canonical_across_three_actions": _CALLER_ONLY_CHILD_DESTRUCTOR_NOT_GENERATED,
    "destructor_interface_state_completed_by_creator": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_requirements_resolved_across_three_callers": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
    "destructor_with_children_known_only_two_callers_up": _DESTRUCTION_CONTRACT_DESTRUCTORS_NOT_RECORDED,
}
_GENERATED_TRACE_TEST_CASES = [
    pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_GENERATED_TRACE_CASE_REASONS[test_case_dir.name],
        )
        if test_case_dir.name in _UNSUPPORTED_GENERATED_TRACE_CASE_REASONS
        else (),
    )
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]
_GENERATED_OPERATION_TRACE_TEST_CASES = [
    pytest.param(
        trace_file.parent,
        id=trace_file.parent.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_UNSUPPORTED_OPERATION_TRACE_CASE_REASONS[trace_file.parent.name],
        )
        if trace_file.parent.name in _UNSUPPORTED_OPERATION_TRACE_CASE_REASONS
        else (),
    )
    for trace_file in sorted(_TESTDATA_ROOT.glob("*/operation_trace.json"))
]
_CONCURRENT_RUNTIME_TEST_CASES = [
    pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=(
                test_case_dir.name
                not in _CONCURRENT_RUNTIME_CASES_WITH_NONDETERMINISTIC_FAILURE
            ),
            reason=_UNSUPPORTED_CONCURRENT_RUNTIME_CASE_REASONS[test_case_dir.name],
        )
        if test_case_dir.name in _UNSUPPORTED_CONCURRENT_RUNTIME_CASE_REASONS
        else (),
    )
    for test_case_dir in _TRACE_TEST_CASE_DIRS
]
_RUNTIME_OPERATION_DEPENDENCY_TEST_CASES = [
    pytest.param(
        test_case_dir,
        id=test_case_dir.name,
        marks=pytest.mark.xfail(
            strict=True,
            reason=_GENERATED_RUNTIME_OPERATION_DEPENDENCIES_DIFFER,
        )
        if test_case_dir.name in _RUNTIME_OPERATION_DEPENDENCY_MISMATCH_CASES
        else (),
    )
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


def _compile_and_check_match(generated_dir: Path) -> driver.CompilationResult:
    result = _compile(generated_dir)
    test_helpers.assert_generated_directory_matches(
        Path("expected_trace"),
        generated_dir,
    )
    return result


def _trace(
    generated_dir: Path,
    trace_file: Path,
    *,
    operation_dependencies_file: Path | None = None,
    max_threads: int | None = None,
) -> list[tracing.OperationTraceRecord]:
    runtime_result = generated_program_runner.run_generated_program(
        generated_dir,
        trace_file=trace_file,
        operation_dependencies_file=operation_dependencies_file,
        max_threads=max_threads,
    )
    if runtime_result.process.returncode != 0:
        pytest.fail(runtime_result.process.stderr)
    return trace_analysis.read_operation_trace(trace_file)


def _assert_trace_respects_resolved_operation_dependencies(
    trace: list[tracing.OperationTraceRecord],
    result: driver.CompilerValidationResult | driver.CompilationResult,
):
    if isinstance(result, driver.CompilationResult):
        entry_action = result.entry_action
    else:
        entry_action = result.program_validation.entry_action
    assert entry_action is not None
    resolved_dependencies = trace_analysis.resolved_operation_dependencies(
        result.operation_graphs,
        entry_action,
    )
    assert collections.Counter(trace) == collections.Counter(
        resolved_dependencies.keys()
    )
    trace_order = {record: index for index, record in enumerate(trace)}
    for operation, dependencies in resolved_dependencies.items():
        for dependency in dependencies:
            assert trace_order[dependency] < trace_order[operation]


@pytest.mark.parametrize(
    "test_case_dir",
    _GENERATED_TRACE_TEST_CASES,
)
def test_generated_trace_matches_expected_artifacts(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    _ = _compile_and_check_match(generated_dir)
    trace = _trace(
        generated_dir,
        tmp_path / "operation_trace.json",
        # Have to do max_threads=1 to make the operation_trace.json's order deterministic.
        max_threads=1,
    )
    assert trace == trace_analysis.read_operation_trace(Path("operation_trace.json"))


@pytest.mark.parametrize("test_case_dir", _GENERATED_OPERATION_TRACE_TEST_CASES)
def test_generated_operation_trace_matches_operation_graph_renderer_ordering(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(test_case_dir.resolve())
    result = driver.Driver().validate_program(Path("test.dfn"))
    assert_no_errors(result.program_validation)
    trace = trace_analysis.read_operation_trace(Path("operation_trace.json"))
    _assert_trace_respects_resolved_operation_dependencies(trace, result)


@pytest.mark.parametrize(
    "test_case_dir",
    _CONCURRENT_RUNTIME_TEST_CASES,
)
def test_concurrent_runtime_respects_resolved_operation_dependencies(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    result = _compile_and_check_match(generated_dir)
    trace = _trace(
        generated_dir,
        tmp_path / "operation_trace.json",
    )
    assert collections.Counter(trace) == collections.Counter(
        trace_analysis.read_operation_trace(Path("operation_trace.json"))
    )
    _assert_trace_respects_resolved_operation_dependencies(trace, result)


@pytest.mark.parametrize(
    "test_case_dir",
    _RUNTIME_OPERATION_DEPENDENCY_TEST_CASES,
)
def test_generated_runtime_operation_dependencies_match_resolved_operation_graph(
    test_case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(test_case_dir.resolve())
    generated_dir = tmp_path / "generated"
    result = _compile(generated_dir)
    operation_dependencies_file = tmp_path / "operation_dependencies.json"
    trace = _trace(
        generated_dir,
        tmp_path / "operation_trace.json",
        operation_dependencies_file=operation_dependencies_file,
        max_threads=1,
    )
    runtime_dependencies = trace_analysis.read_operation_dependencies(
        operation_dependencies_file,
        trace,
    )
    entry_action = result.entry_action
    assert entry_action is not None
    resolved_dependencies = trace_analysis.resolved_operation_dependencies(
        result.operation_graphs,
        entry_action,
    )
    assert runtime_dependencies.transitive() == resolved_dependencies.transitive()
