from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_occupied_requirement_on_input_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/triggered::input)": [],
        "test.create(/triggered::run)": [],
        "triggered.destroy(input)": ["test.create(/triggered::input)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_on_parent_of_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/triggered::input)": [],
        "test.create(/triggered::input::/child)": ["test.create(/triggered::input)"],
        "test.create(/triggered::run)": [],
        "triggered.destroy(input::/child)": ["test.create(/triggered::input::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_on_grandparent_of_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/triggered::input)": [],
        "test.create(/triggered::input::/child)": ["test.create(/triggered::input)"],
        "test.create(/triggered::input::/child::/grandchild)": [
            "test.create(/triggered::input::/child)"
        ],
        "test.create(/triggered::run)": [],
        "triggered.destroy(input::/child::/grandchild)": [
            "test.create(/triggered::input::/child::/grandchild)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_on_an_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/implied)": [],
        "test.create(/triggered::run)": [],
        "triggered.destroy(/implied)": ["test.create(/implied)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_from_an_implied_position_to_an_interface_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/implied)": [],
        "test.create(/triggered::run)": [],
        "triggered.move(/implied, dest)": ["test.create(/implied)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_of_an_implied_position_carries_its_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/implied)": [],
        "test.create(/implied::/child)": ["test.create(/implied)"],
        "test.create(/triggered::run)": [],
        "triggered.move(/implied, dest)": ["test.create(/implied::/child)"],
        "triggered.destroy(dest::/child)": ["triggered.move(/implied, dest)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
