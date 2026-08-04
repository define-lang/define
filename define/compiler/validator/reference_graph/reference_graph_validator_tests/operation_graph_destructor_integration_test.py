import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_DESTRUCTION_CONTRACTS_NOT_RECORDED = (
    "destructors learned through Destruction Contracts are not recorded in the "
    "operation graph"
)
_GUARANTEE_TRIGGER_NOT_RECORDED = (
    "destructor triggers whose preceding operation is a guarantee are not recorded"
)


def test_destructor_independent_chains_and_operation_after_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "test.create(box)#2": ["test.destroy(box)"],
        "destructor.create(first)": ["test.create(box)"],
        "destructor.create(second)": ["test.create(box)"],
        "destructor.destroy(first)": ["destructor.create(first)"],
        "destructor.destroy(second)": ["destructor.create(second)"],
    }


def test_deep_diamond_operations_on_the_same_implied_position_with_destructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_destructor_on_child_carried_by_parent_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_destructor_and_known_children_with_caller_known_occupancy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_destructor_fragments_finish_before_cascade_frees_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


@pytest.mark.xfail(strict=True, reason=_DESTRUCTION_CONTRACTS_NOT_RECORDED)
def test_destructor_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_default_empty_destructor_position_uses_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(carrier)": [],
        "test.create(carrier::/callee::src)": ["test.create(carrier)"],
        "test.create(carrier::/callee::trigger_pos)": ["test.create(carrier)"],
        "callee.destroy(src)": ["destructor.destroy(/marker)"],
        # Only the caller knows that /marker started empty, so its creation of
        # the parent particle supplies the destructor's empty requirement.
        "destructor.create(/marker)": ["test.create(carrier::/callee::src)"],
        "destructor.destroy(/marker)": ["destructor.create(/marker)"],
    }


def test_caller_emptied_destructor_position_uses_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


@pytest.mark.xfail(strict=True, reason=_GUARANTEE_TRIGGER_NOT_RECORDED)
def test_destructor_on_particle_from_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/maker::run)": ["test.create(box)"],
        "maker.create(result)": ["test.create(box)"],
        "destructor.create(_noop)": ["maker.create(result)"],
        "test.destroy(box::/maker::result)": ["maker.create(result)"],
        "test.destroy(box::/maker::run)": ["test.create(box::/maker::run)"],
        "test.destroy(box)": [
            "test.destroy(box::/maker::result)",
            "test.destroy(box::/maker::run)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTION_CONTRACTS_NOT_RECORDED)
def test_destructor_with_children_known_only_two_callers_up(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_multiple_destructors_all_fire_on_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.create(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.create(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTION_CONTRACTS_NOT_RECORDED)
def test_caller_added_destructor_fires_in_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }


def test_multiple_constructors_and_destructors_modify_same_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_multiple_constructors_run_in_parallel_with_destroy_and_destructors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
