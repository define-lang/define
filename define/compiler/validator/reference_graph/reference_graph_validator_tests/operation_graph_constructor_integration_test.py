from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest

_TEST = "action<my.domain.com:my_lib:/test>"


def test_constructor_trigger_inlines_constructor(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct.create(/marker)": ["test.create(box)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multi_level_constructor_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_b.create(/inner)": ["test.create(box)"],
        "construct_c.create(/leaf)": ["construct_b.create(/inner)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_all_fire_on_one_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(/marker_a)": ["test.create(box)"],
        "construct_b.create(/marker_b)": ["test.create(box)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_three_constructors_all_fire_on_one_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "construct_a.create(/marker_a)": ["test.create(box)"],
        "construct_b.create(/marker_b)": ["test.create(box)"],
        "construct_c.create(/marker_c)": ["test.create(box)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_multiple_constructors_run_in_parallel_with_destroy(
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
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_waits_on_unchanged_implied_position_guarantees(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "construct_a.create(/marker)": ["test.create(source)"],
        "construct_a.destroy(/marker)": ["construct_a.create(/marker)"],
        "construct_b.create(/marker)": ["construct_a.destroy(/marker)"],
        "construct_b.destroy(/marker)": ["construct_b.create(/marker)"],
        # Moving the constructed particle waits until both constructors restore
        # their shared implied position to its unchanged empty state.
        "test.move(source, dest)": ["construct_b.destroy(/marker)"],
        "test.create(dest::/marker)": ["test.move(source, dest)"],
        "test.destroy(dest::/marker)": ["test.create(dest::/marker)"],
        "test.destroy(dest)": ["test.destroy(dest::/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
