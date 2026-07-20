from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


def test_constructor_trigger_inlines_constructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "construct.create(/marker)": ["test.create(box)"],
    }


def test_multi_level_constructor_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "construct_b.create(/inner)": ["test.create(box)"],
        "construct_c.create(/leaf)": ["construct_b.create(/inner)"],
    }


def test_multiple_constructors_all_fire_on_one_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "construct_a.create(/marker_a)": ["test.create(box)"],
        "construct_b.create(/marker_b)": ["test.create(box)"],
    }
