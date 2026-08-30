from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest


def test_occupied_requirement_on_input_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/triggered::input)": [],
        "test.create(/triggered::run)": [],
        # The callee's occupied requirement on input is satisfied by the
        # caller's Create.
        "triggered.destroy(input)": ["test.create(/triggered::input)"],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
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
        # The caller supplies both the child and the occupied parent required
        # by the callee's Destroy.
        "triggered.destroy(input::/child)": ["test.create(/triggered::input::/child)"],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
        "test.destroy(/triggered::input)": ["triggered.destroy(input::/child)"],
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
        # The chain of caller Creates satisfies every occupied parent required
        # by the callee's operation on the grandchild.
        "triggered.destroy(input::/child::/grandchild)": [
            "test.create(/triggered::input::/child::/grandchild)"
        ],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
        "test.destroy(/triggered::input::/child)": [
            "triggered.destroy(input::/child::/grandchild)"
        ],
        "test.destroy(/triggered::input)": ["test.destroy(/triggered::input::/child)"],
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
        # Both actions' implied position names refer to the same particle, so
        # the callee's Destroy waits for the caller's Create.
        "triggered.destroy(/implied)": ["test.create(/implied)"],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
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
        # Moving from the shared implied position waits for the caller to fill
        # that position.
        "triggered.move(/implied, dest)": ["test.create(/implied)"],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
        "test.destroy(/triggered::dest)": ["triggered.move(/implied, dest)"],
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
        # The child moves with its parent, so the Move waits on the child's
        # Create and its Destroy at the new name waits on that Move.
        "triggered.move(/implied, dest)": ["test.create(/implied::/child)"],
        "triggered.destroy(dest::/child)": ["triggered.move(/implied, dest)"],
        "triggered.destroy(run)": ["test.create(/triggered::run)"],
        "test.destroy(/triggered::dest)": ["triggered.destroy(dest::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
