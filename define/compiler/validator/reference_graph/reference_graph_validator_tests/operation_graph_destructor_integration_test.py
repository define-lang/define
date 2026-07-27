import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_DESTRUCTORS_NOT_RECORDED = (
    "destructor triggers are not recorded in the operation graph"
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
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
def test_multiple_destructors_all_fire_on_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.destroy(box)": ["test.create(box)"],
        "destruct_a.create(_noop)": ["test.destroy(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.destroy(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
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
        "destructor.create(_noop)": ["callee.destroy(target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box)": [
            "test.create(box::/callee::run)",
            "callee.destroy(target)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
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
        "test.destroy(box)": ["construct_b.move(holder, /marker)"],
        "destruct_a.move(/marker, holder)": ["test.destroy(box)"],
        "destruct_a.move(holder, /marker)": ["destruct_a.move(/marker, holder)"],
        "destruct_b.move(/marker, holder)": ["destruct_a.move(holder, /marker)"],
        "destruct_b.move(holder, /marker)": ["destruct_b.move(/marker, holder)"],
    }


@pytest.mark.xfail(strict=True, reason=_DESTRUCTORS_NOT_RECORDED)
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
        "destruct_a.create(_noop)": ["test.destroy(box)"],
        "destruct_a.destroy(_noop)": ["destruct_a.create(_noop)"],
        "destruct_b.create(_noop)": ["test.destroy(box)"],
        "destruct_b.destroy(_noop)": ["destruct_b.create(_noop)"],
    }
