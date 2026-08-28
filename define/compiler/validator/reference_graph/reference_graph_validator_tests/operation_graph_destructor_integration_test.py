from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest

_DESTRUCTION_CONTRACTS_NOT_RECORDED = (
    "destructors learned through Destruction Contracts are not recorded in the "
    "operation graph"
)
_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED = (
    "caller-added Destructor dependencies are not fully resolved in the Operation Graph"
)
_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED = (
    "caller-introduced child Positions are not merged into the destroyer's "
    "canonical destruction order"
)
_CREATOR_CHILD_ORDER_NOT_PROPAGATED = (
    "the creator's canonical child order is not propagated through multiple callees"
)


def test_destructor_independent_chains_and_operation_after_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "test.create(box)#2": ["test.destroy(box)"],
        "destructor.create(first)": ["test.create(box)"],
        "destructor.create(second)": ["test.create(box)"],
        "destructor.destroy(first)": ["destructor.create(first)"],
        "destructor.destroy(second)": ["destructor.create(second)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_uses_callee_unchanged_guarantee_directly(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destructor.create(/filler::trigger_pos)": ["test.create(box)"],
        "filler.create(/implied)": ["test.create(box)"],
        # Returning the contracted position to its required empty state produces
        # the callee guarantee that the Destructor consumes directly.
        "filler.destroy(/implied)": ["filler.create(/implied)"],
        "filler.destroy(trigger_pos)": ["destructor.create(/filler::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_deep_diamond_operations_on_the_same_implied_position_with_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/left::trigger_pos)": [],
        "test.create(/right::trigger_pos)": [],
        "left.create(/left_child::trigger_pos)": [],
        "left_child.create(/marker)": [],
        "right.create(/right_child::trigger_pos)": [],
        "right_child.destroy(/marker)": ["left_child.create(/marker)"],
        # The caller-supplied occupied requirement both orders destruction and
        # fires the directly known destructor.
        "destructor.create(_noop)": ["left_child.create(/marker)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_diamond_callers_order_added_destructor_around_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/caller_a::trigger_pos)": [],
        "test.create(/caller_b::trigger_pos)": [],
        "caller_a.create(destroyer_particle)": [],
        "caller_a.create(carrier)": [],
        "caller_a.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_a.create(destroyer_particle)",
            "caller_a.create(carrier)",
        ],
        "caller_a.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle)"
        ],
        "caller_a:destroyer.destroy(target)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        # Logical trigger order does not serialize the Destructors' independent
        # Particle Operations.
        "caller_a:destroyer:extra_destructor.create(work)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:extra_destructor.destroy(work)": [
            "caller_a:destroyer:extra_destructor.create(work)"
        ],
        "caller_a:destroyer:known_destructor.create(work)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:known_destructor.destroy(work)": [
            "caller_a:destroyer:known_destructor.create(work)"
        ],
        "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_a.destroy(destroyer_particle)": [
            "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "caller_a:destroyer.destroy(target)",
        ],
        "caller_b.create(destroyer_particle)": [],
        "caller_b.create(carrier)": [],
        "caller_b.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_b.create(destroyer_particle)",
            "caller_b.create(carrier)",
        ],
        "caller_b.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle)"
        ],
        "caller_b:destroyer.destroy(target)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        # The opposite logical trigger order likewise creates no dependency
        # between the independent Particle Operations.
        "caller_b:destroyer:known_destructor.create(work)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:known_destructor.destroy(work)": [
            "caller_b:destroyer:known_destructor.create(work)"
        ],
        "caller_b:destroyer:extra_destructor.create(work)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:extra_destructor.destroy(work)": [
            "caller_b:destroyer:extra_destructor.create(work)"
        ],
        "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_b.destroy(destroyer_particle)": [
            "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "caller_b:destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason="Destructor Contract requirements are not recorded in the Operation Graph",
)
def test_diamond_callers_serialize_added_destructor_around_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/caller_a::trigger_pos)": [],
        "test.create(/caller_b::trigger_pos)": [],
        "caller_a.create(destroyer_particle)": [],
        "caller_a.create(carrier)": [],
        "caller_a.create(carrier::/marker)": ["caller_a.create(carrier)"],
        "caller_a.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_a.create(destroyer_particle)",
            "caller_a.create(carrier::/marker)",
        ],
        "caller_a.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle)"
        ],
        # Both Destructors operate on /marker, so the ordinary position dependency
        # rules serialize their work in reverse quality-assignment order.
        "caller_a:destroyer:extra_destructor.move(/marker, holder)": [
            "caller_a.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_a:destroyer:extra_destructor.move(holder, /marker)": [
            "caller_a:destroyer:extra_destructor.move(/marker, holder)"
        ],
        "caller_a:destroyer:known_destructor.move(/marker, holder)": [
            "caller_a:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_a:destroyer:known_destructor.move(holder, /marker)": [
            "caller_a:destroyer:known_destructor.move(/marker, holder)"
        ],
        "caller_a:destroyer.destroy(target::/marker)": [
            "caller_a:destroyer:known_destructor.move(holder, /marker)"
        ],
        "caller_a:destroyer.destroy(target)": [
            "caller_a:destroyer.destroy(target::/marker)"
        ],
        "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_a.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_a.destroy(destroyer_particle)": [
            "caller_a.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "caller_a:destroyer.destroy(target)",
        ],
        "caller_b.create(destroyer_particle)": [],
        "caller_b.create(carrier)": [],
        "caller_b.create(carrier::/marker)": ["caller_b.create(carrier)"],
        "caller_b.move(carrier, destroyer_particle::/destroyer::target)": [
            "caller_b.create(destroyer_particle)",
            "caller_b.create(carrier::/marker)",
        ],
        "caller_b.create(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle)"
        ],
        # Reversing the quality assignments reverses the dependency between the
        # same two Destructor bodies on this caller's Action Execution.
        "caller_b:destroyer:known_destructor.move(/marker, holder)": [
            "caller_b.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "caller_b:destroyer:known_destructor.move(holder, /marker)": [
            "caller_b:destroyer:known_destructor.move(/marker, holder)"
        ],
        "caller_b:destroyer:extra_destructor.move(/marker, holder)": [
            "caller_b:destroyer:known_destructor.move(holder, /marker)"
        ],
        "caller_b:destroyer:extra_destructor.move(holder, /marker)": [
            "caller_b:destroyer:extra_destructor.move(/marker, holder)"
        ],
        "caller_b:destroyer.destroy(target::/marker)": [
            "caller_b:destroyer:extra_destructor.move(holder, /marker)"
        ],
        "caller_b:destroyer.destroy(target)": [
            "caller_b:destroyer.destroy(target::/marker)"
        ],
        "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "caller_b.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "caller_b.destroy(destroyer_particle)": [
            "caller_b.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "caller_b:destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_ordering_move_retains_independent_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.create(carrier::/shared)": ["test.create(carrier)"],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier::/shared)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target::/shared, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target::/shared)": [
            "destroyer.move(target::/shared, holder)"
        ],
        "destroyer.create(target::/destination)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/destination)": [
            "destroyer.create(target::/destination)"
        ],
        "known_destructor.move(/shared, holder)": [
            "destroyer.move(holder, target::/shared)"
        ],
        "known_destructor.move(holder, /shared)": [
            "known_destructor.move(/shared, holder)"
        ],
        # The Move Rule retains the independent Fill Dependency because the
        # preceding Destructor Guarantee does not depend on it.
        "extra_destructor.move(/shared, /destination)": [
            "known_destructor.move(holder, /shared)",
            "destroyer.destroy(target::/destination)",
        ],
        "extra_destructor.move(/destination, /shared)": [
            "extra_destructor.move(/shared, /destination)"
        ],
        "destroyer.destroy(target::/shared)": [
            "extra_destructor.move(/destination, /shared)"
        ],
        "destroyer.destroy(target)": ["destroyer.destroy(target::/shared)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_ordering_fill_rule(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        # The Fill Rule selects each preceding Destroy as the single most recent
        # operation on /marker.
        "known_destructor.create(/marker)": ["destroyer.destroy(target::/marker)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_caller_destructor_between_two_destroyer_known_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        "later_assigned_destructor.create(/marker)": [
            "destroyer.destroy(target::/marker)"
        ],
        "later_assigned_destructor.destroy(/marker)": [
            "later_assigned_destructor.create(/marker)"
        ],
        # The caller-assigned Destructor's Fill Rule selects the Guarantee from
        # the later-assigned Destructor that precedes it in destruction order.
        "caller_destructor.create(/marker)": [
            "later_assigned_destructor.destroy(/marker)"
        ],
        "caller_destructor.destroy(/marker)": ["caller_destructor.create(/marker)"],
        # The earlier-assigned Destructor's Fill Rule likewise selects the
        # caller-assigned Destructor's Guarantee as its preceding operation.
        "earlier_assigned_destructor.create(/marker)": [
            "caller_destructor.destroy(/marker)"
        ],
        "earlier_assigned_destructor.destroy(/marker)": [
            "earlier_assigned_destructor.create(/marker)"
        ],
        "destroyer.destroy(target)": ["earlier_assigned_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_caller_interleaves_destructors_with_destroyer_known_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.create(target::/marker)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/marker)": ["destroyer.create(target::/marker)"],
        "fifth_destructor.create(/marker)": ["destroyer.destroy(target::/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        # The next directly known Destructor follows the caller-known Destructor
        # assigned after it because destruction reverses assignment order.
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        # The next caller-known Destructor follows the directly known Destructor's
        # final operation on their shared position.
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        # The second directly known Destructor exercises the same transition a
        # second time rather than terminating the interleaved sequence.
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        # The caller-known Destructor assigned first must be the final Destructor
        # to operate on /marker before its parent is destroyed.
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["first_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_ordering_move_retains_independent_empty_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.create(carrier::/origin)": ["test.create(carrier)"],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier::/origin)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target::/origin, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target::/origin)": [
            "destroyer.move(target::/origin, holder)"
        ],
        "destroyer.create(target::/destination)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.destroy(target::/destination)": [
            "destroyer.create(target::/destination)"
        ],
        "known_destructor.create(/destination)": [
            "destroyer.destroy(target::/destination)"
        ],
        "known_destructor.destroy(/destination)": [
            "known_destructor.create(/destination)"
        ],
        # Replacing the target Fill Dependency does not replace the independent
        # Empty Dependency selected for /origin.
        "extra_destructor.move(/origin, /destination)": [
            "known_destructor.destroy(/destination)",
            "destroyer.move(holder, target::/origin)",
        ],
        "extra_destructor.move(/destination, /origin)": [
            "extra_destructor.move(/origin, /destination)"
        ],
        "destroyer.destroy(target::/origin)": [
            "extra_destructor.move(/destination, /origin)"
        ],
        "destroyer.destroy(target)": ["destroyer.destroy(target::/origin)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_ordering_action_parent_rule(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(destroyer_particle)": [],
        "test.create(carrier)": [],
        "test.move(carrier, destroyer_particle::/destroyer::target)": [
            "test.create(destroyer_particle)",
            "test.create(carrier)",
        ],
        "test.create(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle)"
        ],
        "destroyer.move(target, holder)": [
            "test.move(carrier, destroyer_particle::/destroyer::target)"
        ],
        "destroyer.move(holder, target)": ["destroyer.move(target, holder)"],
        # The Fill Rule selects the latest operation on /marker's parent. Modular
        # resolution represents that relationship through the Action Parent Rule.
        "known_destructor.create(/marker)": ["destroyer.move(holder, target)"],
        "known_destructor.destroy(/marker)": ["known_destructor.create(/marker)"],
        "extra_destructor.create(/marker)": ["known_destructor.destroy(/marker)"],
        "extra_destructor.destroy(/marker)": ["extra_destructor.create(/marker)"],
        "destroyer.destroy(target)": ["extra_destructor.destroy(/marker)"],
        "test.destroy(destroyer_particle::/destroyer::trigger_pos)": [
            "test.create(destroyer_particle::/destroyer::trigger_pos)"
        ],
        "test.destroy(destroyer_particle)": [
            "test.destroy(destroyer_particle::/destroyer::trigger_pos)",
            "destroyer.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_child_carried_by_parent_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(staging)": [],
        "test.create(staging::/child)": ["test.create(staging)"],
        "test.move(staging, box)": ["test.create(staging::/child)"],
        # The parent move is the firing Particle Operation for the destructor
        # assigned to the particle in its child position.
        "destructor.create(_noop)": ["test.move(staging, box)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/child)": ["test.move(staging, box)"],
        "test.destroy(box)": ["test.destroy(box::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_and_known_children_with_caller_known_occupancy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker_a)": ["test.create(source)"],
        "test.create(source::/marker_b)": ["test.create(source)"],
        "test.create(source::/maybe_empty)": ["test.create(source)"],
        "test.destroy(source::/maybe_empty)": ["test.create(source::/maybe_empty)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/marker_a)",
            "test.create(source::/marker_b)",
            "test.destroy(source::/maybe_empty)",
        ],
        "middle.move(run::/marker_a, holder_a)": ["test.move(source, /middle::run)"],
        "middle.move(holder_a, run::/marker_a)": [
            "middle.move(run::/marker_a, holder_a)"
        ],
        "middle.move(run::/marker_b, holder_b)": ["test.move(source, /middle::run)"],
        "middle.move(holder_b, run::/marker_b)": [
            "middle.move(run::/marker_b, holder_b)"
        ],
        "middle.create(run::/maybe_empty)": ["test.move(source, /middle::run)"],
        "middle.destroy(run::/maybe_empty)": ["middle.create(run::/maybe_empty)"],
        "middle.move(run, /destroyer::run)": [
            "middle.move(holder_a, run::/marker_a)",
            "middle.move(holder_b, run::/marker_b)",
            "middle.destroy(run::/maybe_empty)",
        ],
        "destroyer.move(run::/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_a, run::/marker_a)": [
            "destroyer.move(run::/marker_a, holder_a)"
        ],
        "destroyer.move(run::/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_b, run::/marker_b)": [
            "destroyer.move(run::/marker_b, holder_b)"
        ],
        # A directly known Destructor executes as an action even when the
        # particles satisfying its occupied requirements came from the caller.
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        # The destruction cascade waits for the Destructor to finish using each
        # caller-supplied child before destroying it.
        "destroyer.destroy(run::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "destroyer.destroy(run::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
        # Caller-known empty occupancy remains available when /destroyer creates
        # a particle in /maybe_empty.
        "destroyer.create(run::/maybe_empty)": ["middle.move(run, /destroyer::run)"],
        "destroyer.destroy(run::/maybe_empty)": ["destroyer.create(run::/maybe_empty)"],
        "destroyer.destroy(run)": [
            "destroyer.destroy(run::/maybe_empty)",
            "destroyer.destroy(run::/marker_b)",
            "destroyer.destroy(run::/marker_a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_fragments_finish_before_cascade_frees_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/marker_a)": ["test.create(box)"],
        "test.create(box::/marker_b)": ["test.create(box)"],
        # The destructor's two occupied implied-position requirements bind
        # independently to the operations that filled their particles.
        "destruct.move(/marker_a, holder_a)": ["test.create(box::/marker_a)"],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": ["test.create(box::/marker_b)"],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        "test.destroy(box::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "test.destroy(box::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
        "test.destroy(box)": [
            "test.destroy(box::/marker_b)",
            "test.destroy(box::/marker_a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_auto_destruction_of_child_with_caller_known_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/extra)"],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # The callee's parent move is also an operation on the child position, so
        # it is the Destructor's most recent Action Parent operation.
        "child_destruct.create(_noop)": ["destroyer.move(run, local)"],
        "child_destruct.destroy(_noop)": ["child_destruct.create(_noop)"],
        # The Destructor does not operate on /extra, so its independent work does
        # not precede the caller-contributed child Destroy.
        "destroyer.destroy(local::/extra)": ["destroyer.move(run, local)"],
        # The contributed child Destroy must finish before automatic destruction
        # empties the local position.
        "destroyer.destroy(local)": ["destroyer.destroy(local::/extra)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_newly_known_children_with_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra_a)": ["test.create(source)"],
        "test.create(source::/extra_b)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": [
            "test.create(source::/extra_a)",
            "test.create(source::/extra_b)",
        ],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # The callee's parent move is the most recent Action Parent operation for
        # each newly known child's independently contributed Destructor.
        "destruct_a.create(_noop_a)": ["destroyer.move(run, local)"],
        "destruct_a.destroy(_noop_a)": ["destruct_a.create(_noop_a)"],
        "destruct_b.create(_noop_b)": ["destroyer.move(run, local)"],
        "destruct_b.destroy(_noop_b)": ["destruct_b.create(_noop_b)"],
        "destroyer.destroy(local::/extra_a)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local::/extra_b)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local)": [
            "destroyer.destroy(local::/extra_b)",
            "destroyer.destroy(local::/extra_a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_passed_particle_with_newly_known_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/extra)"],
        "destroyer.move(run, local)": ["test.move(source, /destroyer::run)"],
        # Discovering child destruction in the same Destruction Contract must
        # not suppress the passed particle's Destructor or its dependency on the
        # callee's most recent Action Parent operation.
        "parent_destruct.create(_noop)": ["destroyer.move(run, local)"],
        "parent_destruct.destroy(_noop)": ["parent_destruct.create(_noop)"],
        "destroyer.destroy(local::/extra)": ["destroyer.move(run, local)"],
        "destroyer.destroy(local)": ["destroyer.destroy(local::/extra)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_newly_known_grandchild_destructor_uses_callee_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/known)": ["test.create(source)"],
        "test.create(source::/known::/extra)": ["test.create(source::/known)"],
        "test.move(source, /destroyer::run)": ["test.create(source::/known::/extra)"],
        "destroyer.move(run::/known, holder)": ["test.move(source, /destroyer::run)"],
        "destroyer.move(holder, run::/known)": ["destroyer.move(run::/known, holder)"],
        # Restoring the child is also an operation on its caller-known grandchild,
        # making it the Destructor's most recent Action Parent operation.
        "grandchild_destruct.create(_noop)": ["destroyer.move(holder, run::/known)"],
        "grandchild_destruct.destroy(_noop)": ["grandchild_destruct.create(_noop)"],
        "destroyer.destroy(run::/known::/extra)": [
            "destroyer.move(holder, run::/known)"
        ],
        # The caller-contributed grandchild Destroy must finish before the child
        # Destroy that the callee can represent.
        "destroyer.destroy(run::/known)": ["destroyer.destroy(run::/known::/extra)"],
        "destroyer.destroy(run)": ["destroyer.destroy(run::/known)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_contributed_child_destructor_depends_on_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.move(held_result, /required)": [
            "destruct.move(/required, held_result)"
        ],
        "destruct.move(/sibling, held_sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destruct.move(held_sibling, /sibling)": [
            "destruct.move(/sibling, held_sibling)"
        ],
        # The caller-known Destructor operates on this callee-guaranteed child
        # before the callee destroys it.
        "destroyer.destroy(parent::/required)": [
            "destruct.move(held_result, /required)"
        ],
        # The same Destructor also operates on the later caller-contributed child
        # before its contributed destruction fragment runs.
        "destroyer.destroy(parent::/sibling)": [
            "destruct.move(held_sibling, /sibling)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "maker.destroy(trigger_pos)",
            "destroyer.destroy(parent::/required)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_known_destructor_precedes_destroyer_known_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /destroyer::parent)": ["test.create(source)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.move(held_result, /required)": [
            "destruct.move(/required, held_result)"
        ],
        # The caller-known Destructor's final Move fills /required before its
        # Destroy.
        "destroyer.destroy(parent::/required)": [
            "destruct.move(held_result, /required)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/required)",
            "maker.destroy(trigger_pos)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_two_caller_known_destructors_precede_same_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(trigger_pos)": ["destroyer.create(parent::/maker::trigger_pos)"],
        "destroyer.move(parent::/maker::result, parent::/required)": [
            "maker.create(result)"
        ],
        "destroyer.move(parent::/required, held_required)": [
            "destroyer.move(parent::/maker::result, parent::/required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        # Both Destructors operate on /required, so the ordinary position
        # dependency rules serialize them in reverse quality-assignment order.
        "destruct_b.move(/required, held_result)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct_b.move(held_result, /required)": [
            "destruct_b.move(/required, held_result)"
        ],
        "destruct_a.move(/required, held_result)": [
            "destruct_b.move(held_result, /required)"
        ],
        "destruct_a.move(held_result, /required)": [
            "destruct_a.move(/required, held_result)"
        ],
        # The final Destructor's last Move fills the child position before the
        # destruction cascade in /destroyer destroys its particle.
        "destroyer.destroy(parent::/required)": [
            "destruct_a.move(held_result, /required)"
        ],
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "maker.destroy(trigger_pos)",
            "destroyer.destroy(parent::/required)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_caller_known_child_destroy_and_destructor_precede_parent_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.create(source::/required::/extra)": ["test.create(source::/required)"],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": [
            "test.create(source::/required::/extra)",
            "test.create(source::/sibling)",
        ],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destruct_required.move(/required, held_required)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct_required.move(held_required, /required)": [
            "destruct_required.move(/required, held_required)"
        ],
        "destruct_sibling.move(/sibling, held_sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destruct_sibling.move(held_sibling, /sibling)": [
            "destruct_sibling.move(/sibling, held_sibling)"
        ],
        # The child Destroy is later on a child of the Destructor's position, so
        # the Empty Rule makes it depend on the Destructor's final operation.
        "destroyer.destroy(parent::/required::/extra)": [
            "destruct_required.move(held_required, /required)"
        ],
        # The later child Destroy replaces the Destructor's operation on its
        # parent during the Empty Rule's Comparison.
        "destroyer.destroy(parent::/required)": [
            "destroyer.destroy(parent::/required::/extra)"
        ],
        "destroyer.destroy(parent::/sibling)": [
            "destruct_sibling.move(held_sibling, /sibling)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "destroyer.destroy(parent::/required)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_contributed_destructor_operates_on_child_of_occupied_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        # The Fill Rule makes the Destructor's Create depend on /destroyer's
        # final Move into the parent position of its empty /required::/work.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required)": ["destruct.destroy(/required::/work)"],
        "destroyer.destroy(parent)": ["destroyer.destroy(parent::/required)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_contributed_destructor_depends_on_callee_move_with_two_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.create(held_required::/left)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.create(held_required::/right)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.destroy(held_required::/left)": [
            "destroyer.create(held_required::/left)"
        ],
        "destroyer.destroy(held_required::/right)": [
            "destroyer.create(held_required::/right)"
        ],
        # The Move Rule retains both sibling child Destroys as independent Empty
        # Dependencies of the Move back to /required.
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.destroy(held_required::/left)",
            "destroyer.destroy(held_required::/right)",
        ],
        # The Fill Rule makes the Destructor's Create depend on the completed
        # Move rather than either of the Move's dependencies directly.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required)": ["destruct.destroy(/required::/work)"],
        "destroyer.destroy(parent)": ["destroyer.destroy(parent::/required)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_child_destroy_depends_on_contributed_destructor_and_sibling_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/required)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/required)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.move(parent::/required, held_required)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.create(held_required::/extra_a)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.create(held_required::/extra_b)": [
            "destroyer.move(parent::/required, held_required)"
        ],
        "destroyer.move(held_required, parent::/required)": [
            "destroyer.create(held_required::/extra_a)",
            "destroyer.create(held_required::/extra_b)",
        ],
        # The Fill Rule makes the Destructor's Create depend on /destroyer's
        # final Move into the parent position of its empty /required::/work.
        "destruct.create(/required::/work)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destruct.destroy(/required::/work)": ["destruct.create(/required::/work)"],
        "destroyer.destroy(parent::/required::/extra_a)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destroyer.destroy(parent::/required::/extra_b)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        # /extra_a, /extra_b, and /work are sibling child positions, so the Empty
        # Rule retains all three final operations before the Destroy of /required.
        "destroyer.destroy(parent::/required)": [
            "destruct.destroy(/required::/work)",
            "destroyer.destroy(parent::/required::/extra_b)",
            "destroyer.destroy(parent::/required::/extra_a)",
        ],
        "destroyer.destroy(parent)": ["destroyer.destroy(parent::/required)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(strict=True, reason=_DESTRUCTION_CONTRACTS_NOT_RECORDED)
def test_destructor_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/marker_a)": ["test.create(source)"],
        "test.create(source::/marker_b)": ["test.create(source)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/marker_a)",
            "test.create(source::/marker_b)",
        ],
        "middle.move(run::/marker_a, holder_a)": ["test.move(source, /middle::run)"],
        "middle.move(holder_a, run::/marker_a)": [
            "middle.move(run::/marker_a, holder_a)"
        ],
        "middle.move(run::/marker_b, holder_b)": ["test.move(source, /middle::run)"],
        "middle.move(holder_b, run::/marker_b)": [
            "middle.move(run::/marker_b, holder_b)"
        ],
        "middle.move(run, /destroyer::run)": [
            "middle.move(holder_a, run::/marker_a)",
            "middle.move(holder_b, run::/marker_b)",
        ],
        "destroyer.move(run::/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_a, run::/marker_a)": [
            "destroyer.move(run::/marker_a, holder_a)"
        ],
        "destroyer.move(run::/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "destroyer.move(holder_b, run::/marker_b)": [
            "destroyer.move(run::/marker_b, holder_b)"
        ],
        # The Destruction Contract from /test propagates through /middle so its
        # caller-known Destructor executes when /destroyer destroys the particle.
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        # /destroyer's destruction cascade waits for the transitively contributed
        # Destructor before destroying the caller-supplied children.
        "destroyer.destroy(run::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "destroyer.destroy(run::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
        "destroyer.destroy(run)": [
            "destroyer.destroy(run::/marker_b)",
            "destroyer.destroy(run::/marker_a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_default_empty_destructor_position_uses_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/callee::src)": ["test.create(carrier)"],
        "test.create(carrier::/callee::trigger_pos)": ["test.create(carrier)"],
        "callee.destroy(src)": ["destructor.destroy(/marker)"],
        # Only the caller knows that /marker started empty, so its creation of
        # the parent particle supplies the destructor's empty requirement.
        "destructor.create(/marker)": ["test.create(carrier::/callee::src)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_emptied_destructor_position_uses_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(source)": [],
        "test.create(source::/marker)": ["test.create(source)"],
        "test.destroy(source::/marker)": ["test.create(source::/marker)"],
        "test.move(source, carrier::/callee::src)": [
            "test.create(carrier)",
            "test.destroy(source::/marker)",
        ],
        "test.create(carrier::/callee::trigger_pos)": ["test.create(carrier)"],
        "callee.destroy(src)": ["destructor.destroy(/marker)"],
        # Only the caller knows that its destroy made /marker empty. The parent
        # move depends on that destroy and supplies the destructor requirement.
        "destructor.create(/marker)": ["test.move(source, carrier::/callee::src)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_moves_callee_guaranteed_particle_before_destroying(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(temp)": ["test.create(box)"],
        "maker.move(temp, result)": ["maker.create(temp)"],
        "test.move(box::/maker::result, held)": ["maker.move(temp, result)"],
        # After the move, it is the operation that fires the destructor.
        "destructor.create(_noop)": ["test.move(box::/maker::result, held)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(held)": ["test.move(box::/maker::result, held)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        # Destroying box also waits for the move that emptied its result position.
        "test.destroy(box)": [
            "test.move(box::/maker::result, held)",
            "test.destroy(box::/maker::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        # The Guarantee both fires the destructor and is the caller operation bound
        # to the destructor's Action Parent Binding Hole.
        "destructor.create(_noop)": ["maker.create(result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/maker::result)": ["maker.create(result)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/maker::result)",
            "test.destroy(box::/maker::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_callee_guarantee_with_child_requirement(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        "maker.create(result::/marker)": ["maker.create(result)"],
        # The child Guarantee is the most recent operation satisfying the
        # Destructor's occupied requirement and follows its Action Parent Create.
        "destructor.move(/marker, holder)": ["maker.create(result::/marker)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "test.destroy(box::/maker::result::/marker)": [
            "destructor.move(holder, /marker)"
        ],
        "test.destroy(box::/maker::result)": [
            "test.destroy(box::/maker::result::/marker)"
        ],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/maker::result)",
            "test.destroy(box::/maker::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destroy_fires_destructor_attached_in_callee_and_surfaced_via_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/make_thing::run)": ["test.create(box)"],
        "make_thing.create(temp)": ["test.create(box)"],
        "make_thing.move(temp, result)": ["make_thing.create(temp)"],
        # The move propagates the destructor even though result has no such constraint.
        "destructor.create(_noop)": ["make_thing.move(temp, result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/make_thing::result)": ["make_thing.move(temp, result)"],
        "test.destroy(box::/make_thing::run)": ["test.create(box::/make_thing::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/make_thing::result)",
            "test.destroy(box::/make_thing::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_attached_in_callee_on_implied_position_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(temp)": ["test.create(box)"],
        "maker.move(temp, /child)": ["maker.create(temp)"],
        # The implied-position guarantee propagates and fires the destructor that
        # /maker attached to the particle.
        "destructor.create(_noop)": ["maker.move(temp, /child)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/child)": ["maker.move(temp, /child)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/child)",
            "test.destroy(box::/maker::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_particle_from_transitive_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::run)": ["test.create(gateway)"],
        "middle.create(box)": ["test.create(gateway)"],
        "middle.create(box::/inner::run)": ["middle.create(box)"],
        "inner.create(result)": ["middle.create(box)"],
        "inner.create(result::/marker)": ["inner.create(result)"],
        # The transitive result Guarantee fires the destructor and is the caller
        # operation bound to the destructor's Action Parent Binding Hole.
        "destructor.create(_noop)": ["inner.create(result)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        # The child guarantee supplies the destructor's occupied requirement.
        "destructor.move(/marker, holder)": ["inner.create(result::/marker)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "test.destroy(gateway::/middle::box::/inner::result::/marker)": [
            "destructor.move(holder, /marker)"
        ],
        "test.destroy(gateway::/middle::box::/inner::result)": [
            "test.destroy(gateway::/middle::box::/inner::result::/marker)"
        ],
        "test.destroy(gateway::/middle::run)": ["test.create(gateway::/middle::run)"],
        "test.destroy(gateway::/middle::box::/inner::run)": [
            "middle.create(box::/inner::run)"
        ],
        "test.destroy(gateway::/middle::box)": [
            "test.destroy(gateway::/middle::box::/inner::result)",
            "test.destroy(gateway::/middle::box::/inner::run)",
        ],
        "test.destroy(gateway)": [
            "test.destroy(gateway::/middle::run)",
            "test.destroy(gateway::/middle::box)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_on_implied_position_from_transitive_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::run)": ["test.create(box)"],
        "middle.create(/inner::run)": ["test.create(box)"],
        "inner.create(/child)": ["test.create(box)"],
        # The transitive implied-position guarantee fires the destructor.
        "destructor.create(_noop)": ["inner.create(/child)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/child)": ["inner.create(/child)"],
        "test.destroy(box::/middle::run)": ["test.create(box::/middle::run)"],
        "test.destroy(box::/inner::run)": ["middle.create(/inner::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/child)",
            "test.destroy(box::/middle::run)",
            "test.destroy(box::/inner::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(strict=True, reason=_DESTRUCTION_CONTRACTS_NOT_RECORDED)
def test_destructor_with_children_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/extra)": ["test.create(source)"],
        "test.create(source::/extra::/marker_a)": ["test.create(source::/extra)"],
        "test.create(source::/extra::/marker_b)": ["test.create(source::/extra)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/extra::/marker_a)",
            "test.create(source::/extra::/marker_b)",
        ],
        "middle.move(run, /destroyer::run)": ["test.move(source, /middle::run)"],
        "destruct.create(work)": ["middle.move(run, /destroyer::run)"],
        "child_destruct.move(/marker_a, holder_a)": [
            "middle.move(run, /destroyer::run)"
        ],
        "child_destruct.move(holder_a, /marker_a)": [
            "child_destruct.move(/marker_a, holder_a)"
        ],
        "child_destruct.move(/marker_b, holder_b)": [
            "middle.move(run, /destroyer::run)"
        ],
        "child_destruct.move(holder_b, /marker_b)": [
            "child_destruct.move(/marker_b, holder_b)"
        ],
        "destroyer.destroy(run::/extra::/marker_a)": [
            "child_destruct.move(holder_a, /marker_a)"
        ],
        "destroyer.destroy(run::/extra::/marker_b)": [
            "child_destruct.move(holder_b, /marker_b)"
        ],
        "destroyer.destroy(run::/extra)": [
            "destroyer.destroy(run::/extra::/marker_b)",
            "destroyer.destroy(run::/extra::/marker_a)",
        ],
        "destroyer.destroy(run)": ["destroyer.destroy(run::/extra)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_destructors_all_fire_on_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.create(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.create(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_destructors_on_particle_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        # One guarantee independently fires both destructors.
        "destruct_a.create(_noop)": ["maker.create(result)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["maker.create(result)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
        "test.destroy(box::/maker::result)": ["maker.create(result)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/maker::result)",
            "test.destroy(box::/maker::run)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_fires_in_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        "destructor.create(_noop)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_fans_out_from_action_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # Both independent Destructor chains receive the same Action Parent
        # dependency from the operation that moved the destroyed particle.
        "destructor.create(work_a)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(work_a)": ["destructor.create(work_a)"],
        "destructor.create(work_b)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(work_b)": ["destructor.create(work_b)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_destructor_with_later_action_execution(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(later_box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(carrier)#2": ["test.move(carrier, box::/callee::target)"],
        "test.move(carrier, later_box::/later::target)": [
            "test.create(later_box)",
            "test.create(carrier)#2",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # The two direct Action Executions independently fire the same
        # caller-contributed Destructor from their respective particle Moves.
        "destructor.create(_noop)": ["test.move(carrier, box::/callee::target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.create(later_box::/later::run)": ["test.create(later_box)"],
        "later.destroy(target)": ["test.move(carrier, later_box::/later::target)"],
        "destructor#2.create(_noop)": ["test.move(carrier, later_box::/later::target)"],
        "destructor#2.destroy(_noop)": ["destructor#2.create(_noop)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/callee::run)",
            "callee.destroy(target)",
        ],
        "test.destroy(later_box::/later::run)": ["test.create(later_box::/later::run)"],
        "test.destroy(later_box)": [
            "test.destroy(later_box::/later::run)",
            "later.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_added_multiple_destructors_fire_in_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(carrier)": [],
        "test.move(carrier, box::/callee::target)": [
            "test.create(box)",
            "test.create(carrier)",
        ],
        "test.create(box::/callee::run)": ["test.create(box)"],
        "callee.destroy(target)": ["test.move(carrier, box::/callee::target)"],
        # The same callee Destroy independently fires both caller-added
        # Destructors from the operation that moved their parent particle.
        "destructor_a.create(work)": ["test.move(carrier, box::/callee::target)"],
        "destructor_a.destroy(work)": ["destructor_a.create(work)"],
        "destructor_b.create(work)": ["test.move(carrier, box::/callee::target)"],
        "destructor_b.destroy(work)": ["destructor_b.create(work)"],
        "test.destroy(box::/callee::run)": ["test.create(box::/callee::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_and_destructors_modify_same_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(/marker)": ["test.create(box)"],
        "construct_b.move(/marker, holder)": ["construct_a.create(/marker)"],
        "construct_b.move(holder, /marker)": ["construct_b.move(/marker, holder)"],
        "destruct_b.move(/marker, holder)": ["construct_b.move(holder, /marker)"],
        "destruct_b.move(holder, /marker)": ["destruct_b.move(/marker, holder)"],
        "destruct_a.move(/marker, holder)": ["destruct_b.move(holder, /marker)"],
        "destruct_a.move(holder, /marker)": ["destruct_a.move(/marker, holder)"],
        "test.destroy(box::/marker)": ["destruct_a.move(holder, /marker)"],
        "test.destroy(box)": ["test.destroy(box::/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_run_in_parallel_with_destroy_and_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(scratch)": ["test.create(box)"],
        "construct_a.destroy(scratch)": ["construct_a.create(scratch)"],
        "construct_b.create(scratch)": ["test.create(box)"],
        "construct_b.destroy(scratch)": ["construct_b.create(scratch)"],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.create(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.create(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_occupied_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_occupied_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fifth)",
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_empty_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "third_destructor.destroy(/third)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_empty_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "fifth_destructor.destroy(/fifth)",
            "fourth_destructor.destroy(/fourth)",
            "third_destructor.destroy(/third)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_occupied_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/first)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_occupied_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/second)",
            "fifth_destructor.destroy(/fifth)",
            "third_destructor.destroy(/third)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_three_destroyer_empty_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/second)",
            "third_destructor.destroy(/third)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_all_positions_five_destroyer_empty_caller_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fifth)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/first)",
            "fourth_destructor.destroy(/fourth)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_three_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_five_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fifth)",
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_three_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "third_destructor.destroy(/third)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_five_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "fifth_destructor.destroy(/fifth)",
            "fourth_destructor.destroy(/fourth)",
            "third_destructor.destroy(/third)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_three_empty_children_between_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.destroy(carrier::/second)": ["test.create(carrier::/second)"],
        "test.move(carrier, /destroyer::target)": ["test.destroy(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.move(/third, holder)": ["destroyer.create(target::/third)"],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["test.move(carrier, /destroyer::target)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": ["destroyer.create(target::/first)"],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/first)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_five_empty_children_between_occupied_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.destroy(carrier::/first)": ["test.create(carrier::/first)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.destroy(carrier::/third)": ["test.create(carrier::/third)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.destroy(carrier::/fifth)": ["test.create(carrier::/fifth)"],
        "test.move(carrier, /destroyer::target)": [
            "test.destroy(carrier::/first)",
            "test.destroy(carrier::/third)",
            "test.destroy(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.create(/fifth)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/fifth)": ["fifth_destructor.create(/fifth)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "third_destructor.create(/third)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.create(target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["test.move(carrier, /destroyer::target)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/second)",
            "fifth_destructor.destroy(/fifth)",
            "third_destructor.destroy(/third)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_three_occupied_children_between_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/second)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": ["test.create(carrier::/second)"],
        "destroyer.create(target::/first)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/first)": ["destroyer.create(target::/first)"],
        "destroyer.create(target::/third)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/third)": ["destroyer.create(target::/third)"],
        "third_destructor.create(/third)": ["destroyer.destroy(target::/third)"],
        "third_destructor.destroy(/third)": ["third_destructor.create(/third)"],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "third_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "second_destructor.move(/second, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "first_destructor.create(/first)": ["destroyer.destroy(target::/first)"],
        "first_destructor.destroy(/first)": ["first_destructor.create(/first)"],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/second)",
            "third_destructor.destroy(/third)",
            "first_destructor.destroy(/first)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_INTRODUCED_CHILD_POSITIONS_NOT_RESOLVED,
)
def test_caller_introduces_five_occupied_children_between_empty_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/first)": ["test.create(carrier)"],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "test.create(carrier::/fifth)": ["test.create(carrier)"],
        "test.move(carrier, /destroyer::target)": [
            "test.create(carrier::/first)",
            "test.create(carrier::/third)",
            "test.create(carrier::/fifth)",
        ],
        "destroyer.create(target::/second)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/second)": ["destroyer.create(target::/second)"],
        "destroyer.create(target::/fourth)": ["test.move(carrier, /destroyer::target)"],
        "destroyer.destroy(target::/fourth)": ["destroyer.create(target::/fourth)"],
        "fifth_destructor.move(/fifth, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "fifth_destructor.create(/marker)": ["test.move(carrier, /destroyer::target)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "fourth_destructor.create(/fourth)": ["destroyer.destroy(target::/fourth)"],
        "fourth_destructor.destroy(/fourth)": ["fourth_destructor.create(/fourth)"],
        "fourth_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "third_destructor.move(/third, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "second_destructor.create(/second)": ["destroyer.destroy(target::/second)"],
        "second_destructor.destroy(/second)": ["second_destructor.create(/second)"],
        "second_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "first_destructor.move(/first, holder)": [
            "test.move(carrier, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        "first_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/fifth)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/first)",
            "fourth_destructor.destroy(/fourth)",
            "second_destructor.destroy(/second)",
            "first_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CREATOR_CHILD_ORDER_NOT_PROPAGATED,
)
def test_creator_reverse_child_order_is_canonical_across_three_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "worker.create(first_interface)": ["test.create(carrier)"],
        "worker.create(second_interface)": ["test.create(carrier)"],
        "test.move(carrier, /middle::target)": [
            "test.create(carrier::/third)",
            "worker.create(first_interface)",
            "worker.create(second_interface)",
        ],
        "middle.create(target::/first)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/second)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/fifth)": ["test.move(carrier, /middle::target)"],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/first)",
            "middle.create(target::/second)",
            "middle.create(target::/fifth)",
        ],
        "destroyer.move(target::/second, second_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.move(second_holder, target::/second)": [
            "destroyer.move(target::/second, second_holder)"
        ],
        "destroyer.create(target::/fourth)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(/first, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "first_destructor.create(/marker)": ["middle.move(target, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "second_destructor.move(/second, holder)": [
            "destroyer.move(second_holder, target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "third_destructor.move(/third, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "destroyer.destroy(target::/worker::second_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target::/worker::first_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["third_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "fifth_destructor.move(/fifth, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        "fifth_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/first)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/worker::second_interface)",
            "destroyer.destroy(target::/worker::first_interface)",
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/fifth)",
            "fifth_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_CREATOR_CHILD_ORDER_NOT_PROPAGATED,
)
def test_creator_nonoverlapping_child_order_is_canonical_across_three_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(carrier)": [],
        "test.create(carrier::/third)": ["test.create(carrier)"],
        "worker.create(first_interface)": ["test.create(carrier)"],
        "worker.create(second_interface)": ["test.create(carrier)"],
        "test.move(carrier, /middle::target)": [
            "test.create(carrier::/third)",
            "worker.create(first_interface)",
            "worker.create(second_interface)",
        ],
        "middle.create(target::/first)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/second)": ["test.move(carrier, /middle::target)"],
        "middle.create(target::/fifth)": ["test.move(carrier, /middle::target)"],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/first)",
            "middle.create(target::/second)",
            "middle.create(target::/fifth)",
        ],
        "destroyer.move(target::/second, second_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.move(second_holder, target::/second)": [
            "destroyer.move(target::/second, second_holder)"
        ],
        "destroyer.create(target::/fourth)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(/first, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "first_destructor.move(holder, /first)": [
            "first_destructor.move(/first, holder)"
        ],
        # The shared Positions Fill and Empty Rules serialize the Destructors
        # in reverse creator assignment order.
        "first_destructor.create(/marker)": ["middle.move(target, /destroyer::target)"],
        "first_destructor.destroy(/marker)": ["first_destructor.create(/marker)"],
        "destroyer.destroy(target::/first)": ["first_destructor.move(holder, /first)"],
        "fourth_destructor.move(/fourth, holder)": [
            "destroyer.create(target::/fourth)"
        ],
        "fourth_destructor.move(holder, /fourth)": [
            "fourth_destructor.move(/fourth, holder)"
        ],
        "fourth_destructor.create(/marker)": ["first_destructor.destroy(/marker)"],
        "fourth_destructor.destroy(/marker)": ["fourth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fourth)": [
            "fourth_destructor.move(holder, /fourth)"
        ],
        "second_destructor.move(/second, holder)": [
            "destroyer.move(second_holder, target::/second)"
        ],
        "second_destructor.move(holder, /second)": [
            "second_destructor.move(/second, holder)"
        ],
        "second_destructor.create(/marker)": ["fourth_destructor.destroy(/marker)"],
        "second_destructor.destroy(/marker)": ["second_destructor.create(/marker)"],
        "destroyer.destroy(target::/second)": [
            "second_destructor.move(holder, /second)"
        ],
        "fifth_destructor.move(/fifth, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "fifth_destructor.move(holder, /fifth)": [
            "fifth_destructor.move(/fifth, holder)"
        ],
        "fifth_destructor.create(/marker)": ["second_destructor.destroy(/marker)"],
        "fifth_destructor.destroy(/marker)": ["fifth_destructor.create(/marker)"],
        "destroyer.destroy(target::/fifth)": ["fifth_destructor.move(holder, /fifth)"],
        "third_destructor.move(/third, holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "third_destructor.move(holder, /third)": [
            "third_destructor.move(/third, holder)"
        ],
        "third_destructor.create(/marker)": ["fifth_destructor.destroy(/marker)"],
        "third_destructor.destroy(/marker)": ["third_destructor.create(/marker)"],
        "destroyer.destroy(target::/third)": ["third_destructor.move(holder, /third)"],
        "destroyer.destroy(target::/worker::second_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target::/worker::first_interface)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/first)",
            "destroyer.destroy(target::/fourth)",
            "destroyer.destroy(target::/second)",
            "destroyer.destroy(target::/fifth)",
            "destroyer.destroy(target::/third)",
            "destroyer.destroy(target::/worker::second_interface)",
            "destroyer.destroy(target::/worker::first_interface)",
            "third_destructor.destroy(/marker)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_direct_destructor_with_mixed_interface_child_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/destructor::occupied_first)": ["test.create(source)"],
        "test.create(source::/destructor::occupied_first::/transitive)": [
            "test.create(source::/destructor::occupied_first)"
        ],
        "test.create(source::/destructor::occupied_last)": ["test.create(source)"],
        "test.move(source, /destroyer::target)": [
            "test.create(source::/destructor::occupied_first::/transitive)",
            "test.create(source::/destructor::occupied_last)",
        ],
        "destructor.move(occupied_first, first_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(first_holder, occupied_first)": [
            "destructor.move(occupied_first, first_holder)"
        ],
        "destructor.move(occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, occupied_first)"
        ],
        "destructor.move(transitive_holder, occupied_first::/transitive)": [
            "destructor.move(occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(empty)": ["test.move(source, /destroyer::target)"],
        "destructor.destroy(empty)": ["destructor.create(empty)"],
        "destructor.move(occupied_last, last_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(last_holder, occupied_last)": [
            "destructor.move(occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/destructor::occupied_last)": [
            "destructor.move(last_holder, occupied_last)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first::/transitive)": [
            "destructor.move(transitive_holder, occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first)": [
            "destroyer.destroy(target::/destructor::occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/destructor::occupied_last)",
            "destroyer.destroy(target::/destructor::occupied_first)",
            "destructor.destroy(empty)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_caller_contributed_destructor_with_mixed_interface_child_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/destructor::occupied_first)": ["test.create(source)"],
        "test.create(source::/destructor::occupied_first::/transitive)": [
            "test.create(source::/destructor::occupied_first)"
        ],
        "test.create(source::/destructor::occupied_last)": ["test.create(source)"],
        "test.move(source, /destroyer::target)": [
            "test.create(source::/destructor::occupied_first::/transitive)",
            "test.create(source::/destructor::occupied_last)",
        ],
        "destructor.move(occupied_first, first_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(first_holder, occupied_first)": [
            "destructor.move(occupied_first, first_holder)"
        ],
        "destructor.move(occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, occupied_first)"
        ],
        "destructor.move(transitive_holder, occupied_first::/transitive)": [
            "destructor.move(occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(empty)": ["test.move(source, /destroyer::target)"],
        "destructor.destroy(empty)": ["destructor.create(empty)"],
        "destructor.move(occupied_last, last_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destructor.move(last_holder, occupied_last)": [
            "destructor.move(occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/destructor::occupied_last)": [
            "destructor.move(last_holder, occupied_last)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first::/transitive)": [
            "destructor.move(transitive_holder, occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first)": [
            "destroyer.destroy(target::/destructor::occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/destructor::occupied_last)",
            "destroyer.destroy(target::/destructor::occupied_first)",
            "destructor.destroy(empty)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_interface_state_completed_by_creator(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/bundle)": [],
        "test.create(/bundle::/destructor::occupied_first)": ["test.create(/bundle)"],
        "test.create(/bundle::/destructor::occupied_first::/transitive)": [
            "test.create(/bundle::/destructor::occupied_first)"
        ],
        "test.move(/bundle, /middle::target)": [
            "test.create(/bundle::/destructor::occupied_first::/transitive)"
        ],
        "middle.create(target::/destructor::occupied_last)": [
            "test.move(/bundle, /middle::target)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.create(target::/destructor::occupied_last)"
        ],
        "destructor.move(occupied_first, first_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(first_holder, occupied_first)": [
            "destructor.move(occupied_first, first_holder)"
        ],
        "destructor.move(occupied_first::/transitive, transitive_holder)": [
            "destructor.move(first_holder, occupied_first)"
        ],
        "destructor.move(transitive_holder, occupied_first::/transitive)": [
            "destructor.move(occupied_first::/transitive, transitive_holder)"
        ],
        "destructor.create(empty)": ["middle.move(target, /destroyer::target)"],
        "destructor.destroy(empty)": ["destructor.create(empty)"],
        "destructor.move(occupied_last, last_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(last_holder, occupied_last)": [
            "destructor.move(occupied_last, last_holder)"
        ],
        "destroyer.destroy(target::/destructor::occupied_last)": [
            "destructor.move(last_holder, occupied_last)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first::/transitive)": [
            "destructor.move(transitive_holder, occupied_first::/transitive)"
        ],
        "destroyer.destroy(target::/destructor::occupied_first)": [
            "destroyer.destroy(target::/destructor::occupied_first::/transitive)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/destructor::occupied_last)",
            "destroyer.destroy(target::/destructor::occupied_first)",
            "destructor.destroy(empty)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_two_destruction_facts_with_distinct_destructor_sets(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_source)": [],
        "test.create(second_source)": [],
        "test.move(first_source, /destroyer::first)": ["test.create(first_source)"],
        "test.move(second_source, /destroyer::second)": ["test.create(second_source)"],
        "test.create(/destroyer::run)": [],
        # Each Destruction Fact resolves only the Destructors assigned to its
        # particle without creating edges between their independent work.
        "extra_destructor.create(work)": ["test.move(first_source, /destroyer::first)"],
        "extra_destructor.destroy(work)": ["extra_destructor.create(work)"],
        "shared_destructor.create(work)": [
            "test.move(first_source, /destroyer::first)"
        ],
        "shared_destructor.destroy(work)": ["shared_destructor.create(work)"],
        "direct_destructor.create(work)": [
            "test.move(first_source, /destroyer::first)"
        ],
        "direct_destructor.destroy(work)": ["direct_destructor.create(work)"],
        "destroyer.destroy(first)": ["test.move(first_source, /destroyer::first)"],
        "shared_destructor#2.create(work)": [
            "test.move(second_source, /destroyer::second)"
        ],
        "shared_destructor#2.destroy(work)": ["shared_destructor#2.create(work)"],
        "destroyer.destroy(second)": ["test.move(second_source, /destroyer::second)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_destroyer_executions_receive_own_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(a_only)": [],
        "test.move(a_only, /destroyer::target)": ["test.create(a_only)"],
        "destructor_a.create(work)": ["test.move(a_only, /destroyer::target)"],
        "destructor_a.destroy(work)": ["destructor_a.create(work)"],
        "destroyer.destroy(target)": ["test.move(a_only, /destroyer::target)"],
        "test.create(a_and_b)": [],
        "test.move(a_and_b, /destroyer::target)": [
            "test.create(a_and_b)",
            "destroyer.destroy(target)",
        ],
        "destructor_a#2.create(work)": ["test.move(a_and_b, /destroyer::target)"],
        "destructor_a#2.destroy(work)": ["destructor_a#2.create(work)"],
        "destructor_b.create(work)": ["test.move(a_and_b, /destroyer::target)"],
        "destructor_b.destroy(work)": ["destructor_b.create(work)"],
        "destroyer#2.destroy(target)": ["test.move(a_and_b, /destroyer::target)"],
        "test.create(b_only)": [],
        "test.move(b_only, /destroyer::target)": [
            "test.create(b_only)",
            "destroyer#2.destroy(target)",
        ],
        "destructor_b#2.create(work)": ["test.move(b_only, /destroyer::target)"],
        "destructor_b#2.destroy(work)": ["destructor_b#2.create(work)"],
        "destroyer#3.destroy(target)": ["test.move(b_only, /destroyer::target)"],
        "test.create(none)": [],
        "test.move(none, /destroyer::target)": [
            "test.create(none)",
            "destroyer#3.destroy(target)",
        ],
        "destroyer#4.destroy(target)": ["test.move(none, /destroyer::target)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_destructor_requirements_resolved_across_three_callers(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/callee_known)": ["test.create(source)"],
        "test.destroy(source::/callee_known)": ["test.create(source::/callee_known)"],
        "test.create(source::/creator_known)": ["test.create(source)"],
        "test.move(source, /middle::target)": [
            "test.destroy(source::/callee_known)",
            "test.create(source::/creator_known)",
        ],
        "middle.create(target::/middle_known)": ["test.move(source, /middle::target)"],
        "middle.destroy(target::/middle_known)": [
            "middle.create(target::/middle_known)"
        ],
        "middle.move(target, /destroyer::target)": [
            "middle.destroy(target::/middle_known)"
        ],
        "middle.create(/destroyer::run)": [],
        "destroyer.create(target::/callee_known)": [
            "middle.move(target, /destroyer::target)"
        ],
        # The callee, middle caller, and creator respectively supply the last
        # known states of these three Destructor requirement Positions.
        "destructor.move(/callee_known, callee_holder)": [
            "destroyer.create(target::/callee_known)"
        ],
        "destructor.move(callee_holder, /callee_known)": [
            "destructor.move(/callee_known, callee_holder)"
        ],
        "destructor.create(/middle_known)": ["middle.move(target, /destroyer::target)"],
        "destructor.destroy(/middle_known)": ["destructor.create(/middle_known)"],
        "destructor.move(/creator_known, creator_holder)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destructor.move(creator_holder, /creator_known)": [
            "destructor.move(/creator_known, creator_holder)"
        ],
        "destroyer.destroy(target::/callee_known)": [
            "destructor.move(callee_holder, /callee_known)"
        ],
        "destroyer.destroy(target::/creator_known)": [
            "destructor.move(creator_holder, /creator_known)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/callee_known)",
            "destroyer.destroy(target::/creator_known)",
            "destructor.destroy(/middle_known)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_callee_child_state_precedes_destructor_knowledge(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.move(source, /middle::target)": ["test.create(source)"],
        "test.create(/middle::trigger)": [],
        "middle.move(target, /destroyer::target)": [
            "test.move(source, /middle::target)"
        ],
        "middle.create(/destroyer::trigger)": [],
        "middle.destroy(trigger)": ["test.create(/middle::trigger)"],
        "destroyer.create(target::/occupied)": [
            "middle.move(target, /destroyer::target)"
        ],
        "destroyer.create(target::/empty)": ["middle.move(target, /destroyer::target)"],
        "destroyer.destroy(target::/empty)": ["destroyer.create(target::/empty)"],
        # The complete Child State originates in /destroyer, but only /middle
        # knows the Destructor assignment and therefore verifies this execution.
        "destructor.move(/occupied, holder)": ["destroyer.create(target::/occupied)"],
        "destructor.move(holder, /occupied)": ["destructor.move(/occupied, holder)"],
        "destructor.create(/empty)": ["destroyer.destroy(target::/empty)"],
        "destructor.destroy(/empty)": ["destructor.create(/empty)"],
        "destroyer.destroy(target::/occupied)": ["destructor.move(holder, /occupied)"],
        "destroyer.destroy(target)": [
            "destructor.destroy(/empty)",
            "destroyer.destroy(target::/occupied)",
        ],
        "destroyer.destroy(trigger)": ["middle.create(/destroyer::trigger)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_direct_and_implied_destructor_executes_once(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/bundle)": [],
        "test.create(/bundle::/marker)": ["test.create(/bundle)"],
        "test.move(/bundle, direct)": ["test.create(/bundle::/marker)"],
        "test.move(direct, /destroyer::target)": ["test.move(/bundle, direct)"],
        # The Position Constraint and the direct destination constraint assign
        # one Destructor quality to the same particle, so destruction creates
        # one Action Execution.
        "destructor.move(/marker, holder)": ["test.move(direct, /destroyer::target)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destroyer.destroy(target::/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destructor_reached_through_two_implication_paths(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/left)": [],
        "test.create(/left::/marker)": ["test.create(/left)"],
        "test.move(/left, /right)": ["test.create(/left::/marker)"],
        "test.move(/right, /destroyer::target)": ["test.move(/left, /right)"],
        # Moving the particle through the second implied Position does not
        # duplicate the Destructor first assigned in /left.
        "destructor.move(/marker, holder)": ["test.move(/right, /destroyer::target)"],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destroyer.destroy(target::/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_nested_caller_contributed_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(outer)": [],
        "outer_destructor.create(inner_destroyer_particle)": ["test.create(outer)"],
        "outer_destructor.create(inner_source)": ["test.create(outer)"],
        "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(inner_destroyer_particle)",
            "outer_destructor.create(inner_source)",
        ],
        "inner_destroyer.destroy(target)": [
            "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor.create(work)": [
            "outer_destructor.move(inner_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor.destroy(work)": ["inner_destructor.create(work)"],
        "outer_destructor.destroy(inner_destroyer_particle)": [
            "inner_destroyer.destroy(target)"
        ],
        "test.destroy(outer)": ["test.create(outer)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_nested_repeated_destructor_with_caller_known_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(outer)": [],
        "outer_destructor.create(inner_destroyer_particle)": ["test.create(outer)"],
        "outer_destructor.create(first_source)": ["test.create(outer)"],
        "outer_destructor.create(first_source::/extra)": [
            "outer_destructor.create(first_source)"
        ],
        "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(inner_destroyer_particle)",
            "outer_destructor.create(first_source::/extra)",
        ],
        "inner_destructor_a.create(work_a)": [
            "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_a.destroy(work_a)": ["inner_destructor_a.create(work_a)"],
        "inner_destroyer.destroy(target::/extra)": [
            "outer_destructor.move(first_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destroyer.destroy(target)": ["inner_destroyer.destroy(target::/extra)"],
        "outer_destructor.create(second_source)": ["test.create(outer)"],
        "outer_destructor.create(second_source::/extra)": [
            "outer_destructor.create(second_source)"
        ],
        "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)": [
            "outer_destructor.create(second_source::/extra)",
            "inner_destroyer.destroy(target)",
        ],
        "inner_destructor_a#2.create(work_a)": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_a#2.destroy(work_a)": ["inner_destructor_a#2.create(work_a)"],
        "inner_destructor_b.create(work_b)": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destructor_b.destroy(work_b)": ["inner_destructor_b.create(work_b)"],
        "inner_destroyer#2.destroy(target::/extra)#2": [
            "outer_destructor.move(second_source, inner_destroyer_particle::/inner_destroyer::target)"
        ],
        "inner_destroyer#2.destroy(target)": [
            "inner_destroyer#2.destroy(target::/extra)#2"
        ],
        "outer_destructor.destroy(inner_destroyer_particle)": [
            "inner_destroyer#2.destroy(target)"
        ],
        "test.destroy(outer)": ["test.create(outer)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_executions_each_destroy_two_particles(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_a)": [],
        "test.create(first_none)": [],
        "test.move(first_a, /destroyer::first)": ["test.create(first_a)"],
        "test.move(first_none, /destroyer::second)": ["test.create(first_none)"],
        "test.create(/destroyer::run)": [],
        "destroyer.move(run, used_run)": ["test.create(/destroyer::run)"],
        "destroyer.destroy(used_run)": ["destroyer.move(run, used_run)"],
        "destructor_a.create(work_a)": ["test.move(first_a, /destroyer::first)"],
        "destructor_a.destroy(work_a)": ["destructor_a.create(work_a)"],
        "destroyer.destroy(first)": ["test.move(first_a, /destroyer::first)"],
        "destroyer.destroy(second)": ["test.move(first_none, /destroyer::second)"],
        "test.create(second_b)": [],
        "test.create(second_a_and_b)": [],
        "test.move(second_b, /destroyer::first)": [
            "test.create(second_b)",
            "destroyer.destroy(first)",
        ],
        "test.move(second_a_and_b, /destroyer::second)": [
            "test.create(second_a_and_b)",
            "destroyer.destroy(second)",
        ],
        "test.create(/destroyer::run)#2": ["destroyer.move(run, used_run)"],
        "destroyer#2.move(run, used_run)": ["test.create(/destroyer::run)#2"],
        "destroyer#2.destroy(used_run)": ["destroyer#2.move(run, used_run)"],
        # The second Action Execution's two Destruction Facts receive different
        # contribution sets, and neither fact acquires dependencies from the
        # first execution's Destructor.
        "destructor_b.create(work_b)": ["test.move(second_b, /destroyer::first)"],
        "destructor_b.destroy(work_b)": ["destructor_b.create(work_b)"],
        "destroyer#2.destroy(first)": ["test.move(second_b, /destroyer::first)"],
        "destructor_a#2.create(work_a)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
        "destructor_a#2.destroy(work_a)": ["destructor_a#2.create(work_a)"],
        "destructor_b#2.create(work_b)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
        "destructor_b#2.destroy(work_b)": ["destructor_b#2.create(work_b)"],
        "destroyer#2.destroy(second)": [
            "test.move(second_a_and_b, /destroyer::second)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


@pytest.mark.xfail(
    strict=True,
    reason=_DESTRUCTOR_OPERATION_DEPENDENCIES_NOT_RESOLVED,
)
def test_separate_child_contract_paths(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(left_source)": [],
        "test.create(left_source::/extra)": ["test.create(left_source)"],
        "test.move(left_source, source::/left)": [
            "test.create(source)",
            "test.create(left_source::/extra)",
        ],
        "test.create(right_source)": [],
        "test.move(right_source, source::/right)": [
            "test.create(source)",
            "test.create(right_source)",
        ],
        "test.move(source, /destroyer::target)": [
            "test.move(left_source, source::/left)",
            "test.move(right_source, source::/right)",
        ],
        "destroyer.move(target::/left, left_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destroyer.move(left_holder, target::/left)": [
            "destroyer.move(target::/left, left_holder)"
        ],
        "destroyer.move(target::/right, right_holder)": [
            "test.move(source, /destroyer::target)"
        ],
        "destroyer.move(right_holder, target::/right)": [
            "destroyer.move(target::/right, right_holder)"
        ],
        # The parent Destructor and the caller-known child Destroy share the
        # /left path, while /right's Destructor remains an independent chain.
        "parent_destructor.move(/left, holder)": [
            "destroyer.move(left_holder, target::/left)"
        ],
        "parent_destructor.move(holder, /left)": [
            "parent_destructor.move(/left, holder)"
        ],
        "destroyer.destroy(target::/left::/extra)": [
            "parent_destructor.move(holder, /left)"
        ],
        "destroyer.destroy(target::/left)": [
            "destroyer.destroy(target::/left::/extra)"
        ],
        "child_destructor.create(work)": [
            "destroyer.move(right_holder, target::/right)"
        ],
        "child_destructor.destroy(work)": ["child_destructor.create(work)"],
        "destroyer.destroy(target::/right)": [
            "destroyer.move(right_holder, target::/right)"
        ],
        "destroyer.destroy(target)": [
            "destroyer.destroy(target::/left)",
            "destroyer.destroy(target::/right)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_destructor_uses_distinct_requirement_sources(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first_source)": [],
        "test.create(first_source::/marker)": ["test.create(first_source)"],
        "test.move(first_source, /destroyer::target)": [
            "test.create(first_source::/marker)"
        ],
        "destructor.move(/marker, holder)": [
            "test.move(first_source, /destroyer::target)"
        ],
        "destructor.move(holder, /marker)": ["destructor.move(/marker, holder)"],
        "destroyer.destroy(target::/marker)": ["destructor.move(holder, /marker)"],
        "destroyer.destroy(target)": ["destroyer.destroy(target::/marker)"],
        "test.create(second_source)": [],
        "test.create(second_source::/marker)": ["test.create(second_source)"],
        "test.move(second_source, /destroyer::target)": [
            "test.create(second_source::/marker)",
            "destroyer.destroy(target)",
        ],
        # Each Destructor Action Execution receives the parent Move belonging
        # to its own destroyed particle as its occupied requirement dependency.
        "destructor#2.move(/marker, holder)": [
            "test.move(second_source, /destroyer::target)"
        ],
        "destructor#2.move(holder, /marker)": ["destructor#2.move(/marker, holder)"],
        "destroyer#2.destroy(target::/marker)#2": [
            "destructor#2.move(holder, /marker)"
        ],
        "destroyer#2.destroy(target)": ["destroyer#2.destroy(target::/marker)#2"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
