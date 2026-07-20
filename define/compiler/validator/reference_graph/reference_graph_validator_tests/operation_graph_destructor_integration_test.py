import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_DESTRUCTORS_NOT_RECORDED = (
    "destructor triggers are not recorded in the operation graph"
)


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
        "callee.destroy(target)": ["test.create(box::/callee::run)"],
        "destructor.create(_noop)": ["callee.destroy(target)"],
        "destructor.destroy(_noop)": ["destructor.create(_noop)"],
        "test.destroy(box)": [
            "test.create(box)",
            "test.create(box::/callee::run)",
        ],
    }
