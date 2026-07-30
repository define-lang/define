from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_single_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(item)": [],
    }


def test_two_dependent_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(item)": [],
        "test.move(item, dest)": ["test.create(item)"],
    }


def test_three_operation_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(item)": [],
        "test.move(item, dest)": ["test.create(item)"],
        "test.destroy(dest)": ["test.move(item, dest)"],
    }


def test_repeated_operation_on_same_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(item)": [],
        "test.destroy(item)": ["test.create(item)"],
        "test.create(item)#2": ["test.destroy(item)"],
    }


def test_two_parallel_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(a)": [],
        "test.create(b)": [],
        "test.destroy(a)": ["test.create(a)"],
        "test.destroy(b)": ["test.create(b)"],
    }


def test_three_parallel_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(a)": [],
        "test.create(b)": [],
        "test.create(c)": [],
        "test.destroy(a)": ["test.create(a)"],
        "test.destroy(b)": ["test.create(b)"],
        "test.destroy(c)": ["test.create(c)"],
    }


def test_join_operation_waits_on_two_predecessors(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(a)": [],
        "test.create(b)": [],
        "test.destroy(b)": ["test.create(b)"],
        "test.move(a, b)": ["test.create(a)", "test.destroy(b)"],
    }


def test_fan_out_two_operations_depend_on_one(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(a)": [],
        "test.move(a, b)": ["test.create(a)"],
        "test.create(a)#2": ["test.move(a, b)"],
        "test.destroy(b)": ["test.move(a, b)"],
    }


def test_multiway_join_and_fan_out(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/a)": ["test.create(box)"],
        "test.create(box::/b)": ["test.create(box)"],
        "test.destroy(box::/a)": ["test.create(box::/a)"],
        "test.destroy(box::/b)": ["test.create(box::/b)"],
        "test.destroy(box)": [
            "test.destroy(box::/b)",
            "test.destroy(box::/a)",
        ],
    }


def test_destroy_reduces_to_the_deepest_touched_descendant(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.create(box::/child::/grandchild)": ["test.create(box::/child)"],
        "test.destroy(box::/child::/grandchild)": [
            "test.create(box::/child::/grandchild)",
        ],
        "test.destroy(box::/child)": [
            "test.destroy(box::/child::/grandchild)",
        ],
        "test.destroy(box)": ["test.destroy(box::/child)"],
    }


def test_destroy_reduces_its_own_position_create_edge(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.destroy(box::/child)": ["test.create(box::/child)"],
        "test.destroy(box)": ["test.destroy(box::/child)"],
    }


def test_destroy_excludes_an_earlier_move_reached_through_a_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, box::/target)": ["test.create(box::/origin)"],
        "test.destroy(box::/target)": ["test.move(box::/origin, box::/target)"],
        "test.destroy(box)": ["test.destroy(box::/target)"],
    }


def test_move_excludes_an_earlier_move_reached_through_a_child_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, box::/target)": ["test.create(box::/origin)"],
        "test.destroy(box::/target)": ["test.move(box::/origin, box::/target)"],
        "test.move(box, holder)": ["test.destroy(box::/target)"],
        "test.destroy(holder)": ["test.move(box, holder)"],
    }


def test_destroy_excludes_an_earlier_move_reached_through_a_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, box::/target)": ["test.create(box::/origin)"],
        "test.move(box::/target, holder)": ["test.move(box::/origin, box::/target)"],
        "test.destroy(box)": ["test.move(box::/target, holder)"],
        "test.destroy(holder)": ["test.move(box::/target, holder)"],
    }


def test_move_excludes_an_earlier_move_reached_through_a_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, box::/middle)": ["test.create(box::/origin)"],
        "test.move(box::/middle, box::/target)": [
            "test.move(box::/origin, box::/middle)"
        ],
        "test.move(box, holder)": ["test.move(box::/middle, box::/target)"],
        "test.destroy(holder::/target)": ["test.move(box, holder)"],
        "test.destroy(holder)": ["test.destroy(holder::/target)"],
    }


def test_newer_parent_operation_supersedes_an_older_child_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.create(box::/origin::/deep)": ["test.create(box::/origin)"],
        "test.move(box::/origin, box::/target)": ["test.create(box::/origin::/deep)"],
        "test.move(box, holder)": ["test.move(box::/origin, box::/target)"],
        "test.destroy(holder::/target::/deep)": ["test.move(box, holder)"],
        "test.destroy(holder::/target)": ["test.destroy(holder::/target::/deep)"],
        "test.destroy(holder)": ["test.destroy(holder::/target)"],
    }


def test_refill_does_not_repeat_the_ancestor_edge(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.destroy(parent::/child)": ["test.create(parent::/child)"],
        "test.create(parent::/child)#2": ["test.destroy(parent::/child)"],
    }


def test_empty_after_ancestor_move_refill_waits_on_the_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.destroy(box::/child)": ["test.create(box::/child)"],
        "test.destroy(box)": ["test.destroy(box::/child)"],
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, box)": [
            "test.destroy(box)",
            "test.create(source::/child)",
        ],
        "test.destroy(box::/child)#2": ["test.move(source, box)"],
        "test.destroy(box)#2": ["test.destroy(box::/child)#2"],
    }


def test_second_move_of_a_carried_child_waits_on_the_first_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.move(box, basket)": ["test.create(box::/child)"],
        "test.move(basket, crate)": ["test.move(box, basket)"],
    }


def test_deep_ancestor_move_refill_reduces_the_whole_stale_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/mid)": ["test.create(box)"],
        "test.create(box::/mid::/leaf)": ["test.create(box::/mid)"],
        "test.destroy(box::/mid::/leaf)": ["test.create(box::/mid::/leaf)"],
        "test.destroy(box::/mid)": ["test.destroy(box::/mid::/leaf)"],
        "test.destroy(box)": ["test.destroy(box::/mid)"],
        "test.create(source)": [],
        "test.create(source::/mid)": ["test.create(source)"],
        "test.create(source::/mid::/leaf)": ["test.create(source::/mid)"],
        "test.move(source, box)": [
            "test.destroy(box)",
            "test.create(source::/mid::/leaf)",
        ],
        "test.destroy(box::/mid::/leaf)#2": ["test.move(source, box)"],
        "test.destroy(box::/mid)#2": ["test.destroy(box::/mid::/leaf)#2"],
        "test.destroy(box)#2": ["test.destroy(box::/mid)#2"],
    }


def test_move_parent_waits_on_touched_descendants(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(src)": [],
        "test.create(src::/child)": ["test.create(src)"],
        "test.move(src, dest)": ["test.create(src::/child)"],
        "test.destroy(dest::/child)": ["test.move(src, dest)"],
    }


def test_move_between_child_positions_does_not_repeat_parent_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, box::/destination)": ["test.create(box::/origin)"],
    }


def test_move_between_child_positions_uses_source_child_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.create(box::/origin::/child)": ["test.create(box::/origin)"],
        "test.move(box::/origin, box::/destination)": [
            "test.create(box::/origin::/child)"
        ],
    }


def test_move_between_child_positions_uses_independent_source_child_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.create(box::/origin::/first)": ["test.create(box::/origin)"],
        "test.create(box::/origin::/second)": ["test.create(box::/origin)"],
        "test.move(box::/origin, box::/destination)": [
            "test.create(box::/origin::/first)",
            "test.create(box::/origin::/second)",
        ],
    }


def test_move_between_child_positions_does_not_repeat_move_that_filled_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(incoming)": [],
        "test.move(incoming, box)": ["test.create(incoming)"],
        "test.create(box::/origin)": ["test.move(incoming, box)"],
        "test.move(box::/origin, box::/destination)": ["test.create(box::/origin)"],
    }


def test_move_into_emptied_target_waits_on_the_target_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(dest)": [],
        "test.create(dest::/child)": ["test.create(dest)"],
        "test.destroy(dest::/child)": ["test.create(dest::/child)"],
        "test.destroy(dest)": ["test.destroy(dest::/child)"],
        "test.create(src)": [],
        "test.create(src::/child)": ["test.create(src)"],
        "test.move(src, dest)": [
            "test.destroy(dest)",
            "test.create(src::/child)",
        ],
    }


def test_auto_destruction_records_destroy_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(first)": [],
        "test.create(second)": [],
        "test.destroy(second)": ["test.create(second)"],
        "test.destroy(first)": ["test.create(first)"],
    }


def test_create_and_destroy_of_an_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/implied)": [],
        "test.destroy(/implied)": ["test.create(/implied)"],
    }


def test_operations_on_a_child_of_an_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/implied)": [],
        "test.create(/implied::/child)": ["test.create(/implied)"],
        "test.destroy(/implied::/child)": ["test.create(/implied::/child)"],
        "test.destroy(/implied)": ["test.destroy(/implied::/child)"],
    }


def test_move_from_an_interface_position_to_an_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.move(source, /implied)": ["test.create(source)"],
    }


def test_auto_destruction_leaves_the_implied_position_alone(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(temporary)": [],
        "test.create(/implied)": [],
        "test.destroy(temporary)": ["test.create(temporary)"],
    }


def test_destruction_cascade_branches_at_siblings_and_joins_at_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.create(box::/child::/grandchild)": ["test.create(box::/child)"],
        "test.create(box::/sibling)": ["test.create(box)"],
        "test.destroy(box::/child::/grandchild)": [
            "test.create(box::/child::/grandchild)",
        ],
        "test.destroy(box::/child)": [
            "test.destroy(box::/child::/grandchild)",
        ],
        "test.destroy(box::/sibling)": ["test.create(box::/sibling)"],
        "test.destroy(box)": [
            "test.destroy(box::/sibling)",
            "test.destroy(box::/child)",
        ],
    }


def test_destruction_cascade_routes_prior_empty_descendant_to_its_particle(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.create(box::/child::/grandchild)": ["test.create(box::/child)"],
        "test.destroy(box::/child::/grandchild)": [
            "test.create(box::/child::/grandchild)",
        ],
        "test.destroy(box::/child)": [
            "test.destroy(box::/child::/grandchild)",
        ],
        "test.destroy(box)": ["test.destroy(box::/child)"],
    }


def test_destruction_cascade_omits_known_empty_interface_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(parent)": [],
        "test.create(parent::/child)": ["test.create(parent)"],
        "test.move(parent::/child, destination)": ["test.create(parent::/child)"],
        "test.destroy(parent)": ["test.move(parent::/child, destination)"],
    }


def test_destruction_cascade_omits_known_empty_implied_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.move(/parent::/child, destination)": ["test.create(/parent::/child)"],
        "test.destroy(/parent)": ["test.move(/parent::/child, destination)"],
    }


def test_destruction_cascade_branches_from_one_preceding_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.create(source::/b)": ["test.create(source)"],
        "test.move(source, destination)": [
            "test.create(source::/a)",
            "test.create(source::/b)",
        ],
        "test.destroy(destination::/a)": ["test.move(source, destination)"],
        "test.destroy(destination::/b)": ["test.move(source, destination)"],
        "test.destroy(destination)": [
            "test.destroy(destination::/b)",
            "test.destroy(destination::/a)",
        ],
    }
