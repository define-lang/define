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
        "test.move(source, /middle::run)": [
            "test.create(source::/marker_a)",
            "test.create(source::/marker_b)",
        ],
        "middle.move(run, /destroyer::run)": ["test.move(source, /middle::run)"],
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
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
        "destroyer.destroy(run::/marker_a)": ["destruct.move(holder_a, /marker_a)"],
        "destroyer.destroy(run::/marker_b)": ["destruct.move(holder_b, /marker_b)"],
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
        "destruct.move(/maker::result, held_result)": ["maker.create(result)"],
        "destruct.move(held_result, /maker::result)": [
            "destruct.move(/maker::result, held_result)"
        ],
        "destruct.move(/sibling, held_sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destruct.move(held_sibling, /sibling)": [
            "destruct.move(/sibling, held_sibling)"
        ],
        # The caller-known destructor operates on this callee-guaranteed child
        # before the callee destroys it.
        "destroyer.destroy(parent::/maker::result)": [
            "destruct.move(held_result, /maker::result)"
        ],
        "destroyer.destroy(parent::/maker::trigger_pos)": [
            "destroyer.create(parent::/maker::trigger_pos)"
        ],
        # The same destructor also operates on the later caller-contributed child
        # before its contributed destruction fragment runs.
        "destroyer.destroy(parent::/sibling)": [
            "destruct.move(held_sibling, /sibling)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "destroyer.destroy(parent::/maker::result)",
            "destroyer.destroy(parent::/maker::trigger_pos)",
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
        "destruct.move(/maker::result, held_result)": ["maker.create(result)"],
        "destruct.move(held_result, /maker::result)": [
            "destruct.move(/maker::result, held_result)"
        ],
        # The caller-known Destructor's final Move fills /maker::result before
        # its Destroy.
        "destroyer.destroy(parent::/maker::result)": [
            "destruct.move(held_result, /maker::result)"
        ],
        "destroyer.destroy(parent::/maker::trigger_pos)": [
            "destroyer.create(parent::/maker::trigger_pos)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/maker::result)",
            "destroyer.destroy(parent::/maker::trigger_pos)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


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
        "destruct_a.move(/maker::result, held_result)": ["maker.create(result)"],
        "destruct_a.move(held_result, /maker::result)": [
            "destruct_a.move(/maker::result, held_result)"
        ],
        "destruct_b.move(/maker::result, held_result)": ["maker.create(result)"],
        "destruct_b.move(held_result, /maker::result)": [
            "destruct_b.move(/maker::result, held_result)"
        ],
        # Both caller-known Destructors' final Moves must fill the child position
        # before the destruction cascade in /destroyer destroys its particle.
        "destroyer.destroy(parent::/maker::result)": [
            "destruct_b.move(held_result, /maker::result)",
            "destruct_a.move(held_result, /maker::result)",
        ],
        "destroyer.destroy(parent::/maker::trigger_pos)": [
            "destroyer.create(parent::/maker::trigger_pos)"
        ],
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "destroyer.destroy(parent::/maker::result)",
            "destroyer.destroy(parent::/maker::trigger_pos)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


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
        # Both the caller-contributed child Destroy and the Destructor's final
        # operation must precede destruction of /required.
        "destroyer.destroy(parent::/required::/extra)": [
            "destroyer.move(held_required, parent::/required)"
        ],
        "destroyer.destroy(parent::/required)": [
            "destroyer.destroy(parent::/required::/extra)",
            "destruct_required.move(held_required, /required)",
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
        "middle.move(run, /destroyer::run)": ["test.move(source, /middle::run)"],
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
        "destruct.move(/marker_a, holder_a)": [
            "destroyer.move(holder_a, run::/marker_a)"
        ],
        "destruct.move(holder_a, /marker_a)": ["destruct.move(/marker_a, holder_a)"],
        "destruct.move(/marker_b, holder_b)": [
            "destroyer.move(holder_b, run::/marker_b)"
        ],
        "destruct.move(holder_b, /marker_b)": ["destruct.move(/marker_b, holder_b)"],
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
