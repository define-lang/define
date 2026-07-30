from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_destroy_of_the_trigger_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/triggered::run)": [],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
    }


def test_destroy_of_the_trigger_position_waits_on_its_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /triggered::run)": ["test.create(source::/child)"],
        "triggered.destroy(run::/child)": ["test.move(source, /triggered::run)"],
        "triggered.destroy(run)": ["triggered.destroy(run::/child)"],
    }


def test_move_of_the_trigger_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/triggered::run)": [],
        "triggered.move(run, dest)": ["test.create(/triggered::run)"],
    }


def test_move_of_the_trigger_particle_into_a_local_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/triggered::run)": [],
        "triggered.move(run, local)": ["test.create(/triggered::run)"],
        "triggered.destroy(local)": ["triggered.move(run, local)"],
    }


def test_move_of_the_trigger_particle_into_an_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/triggered::run)": [],
        "triggered.move(run, /implied)": ["test.create(/triggered::run)"],
    }


def test_operation_on_a_child_of_the_trigger_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /triggered::run)": ["test.create(source::/child)"],
        "triggered.destroy(run::/child)": ["test.move(source, /triggered::run)"],
    }


def test_destroy_of_trigger_particle_conditionally_destroys_unknown_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.move(source, /triggered::run)": ["test.create(source::/a)"],
        "triggered.move(run, /target)": ["test.move(source, /triggered::run)"],
        "triggered.destroy_if_occupied(/target::/b)": ["triggered.move(run, /target)"],
        "triggered.destroy_if_occupied(/target::/a)": ["triggered.move(run, /target)"],
        "triggered.destroy(/target)": [
            "triggered.destroy_if_occupied(/target::/b)",
            "triggered.destroy_if_occupied(/target::/a)",
        ],
    }
