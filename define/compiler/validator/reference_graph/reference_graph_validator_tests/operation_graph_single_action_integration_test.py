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


def test_move_chain_returning_to_first_position_has_minimal_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(a)": [],
        "test.move(a, b)": ["test.create(a)"],
        "test.move(b, c)": ["test.move(a, b)"],
        "test.move(c, d)": ["test.move(b, c)"],
        "test.move(d, a)": ["test.move(c, d)"],
        "test.destroy(a)": ["test.move(d, a)"],
    }


def test_move_excludes_create_fill_dependency_reached_through_source_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.move(box::/item, holder)": ["test.create(box::/item)"],
        "test.create(holder::/payload)": ["test.move(box::/item, holder)"],
        # The source Create already reaches the operation required to fill the target.
        "test.move(holder::/payload, box::/destination)": [
            "test.create(holder::/payload)"
        ],
    }


def test_move_excludes_fill_dependency_reached_through_replaced_source_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.move(box::/item, holder)": ["test.create(box::/item)"],
        "test.destroy(holder)": ["test.move(box::/item, holder)"],
        "test.create(holder)": ["test.destroy(holder)"],
        # The source Create already reaches the operation required to fill the target.
        "test.move(holder, box::/destination)": ["test.create(holder)"],
    }


def test_move_excludes_create_fill_dependency_reached_through_source_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.create(box::/item::/payload)": ["test.create(box::/item)"],
        "test.move(box::/item, holder)": ["test.create(box::/item::/payload)"],
        "test.destroy(holder::/payload)": ["test.move(box::/item, holder)"],
        # The source Destroy already reaches the operation required to fill the target.
        "test.move(holder, box::/destination)": ["test.destroy(holder::/payload)"],
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


def test_destroy_excludes_earlier_child_move_reached_through_later_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/origin)": ["test.create(box)"],
        "test.move(box::/origin, holder_a)": ["test.create(box::/origin)"],
        "test.move(holder_a, box::/middle)": ["test.move(box::/origin, holder_a)"],
        "test.move(box::/middle, box::/target)": ["test.move(holder_a, box::/middle)"],
        "test.move(box::/target, holder_c)": ["test.move(box::/middle, box::/target)"],
        # The final child Move already reaches the Move that emptied origin, so the
        # Empty Rule excludes the earlier Move from the Destroy's dependencies.
        "test.destroy(box)": ["test.move(box::/target, holder_c)"],
        "test.destroy(holder_c)": ["test.move(box::/target, holder_c)"],
    }


def test_move_excludes_create_on_child_reached_through_parent_move_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.move(box, holder_a)": ["test.create(box::/item)"],
        "test.move(holder_a, holder_b)": ["test.move(box, holder_a)"],
        # The final parent Move already reaches the earlier child Create.
        "test.move(holder_b, holder_c)": ["test.move(holder_a, holder_b)"],
        "test.destroy(holder_c::/item)": ["test.move(holder_b, holder_c)"],
        "test.destroy(holder_c)": ["test.destroy(holder_c::/item)"],
    }


def test_move_excludes_transitive_child_create_reached_through_parent_move_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.create(box::/item::/deep)": ["test.create(box::/item)"],
        "test.move(box, holder_a)": ["test.create(box::/item::/deep)"],
        "test.move(holder_a, holder_b)": ["test.move(box, holder_a)"],
        # The final parent Move already reaches the transitive child Create.
        "test.move(holder_b, holder_c)": ["test.move(holder_a, holder_b)"],
        "test.destroy(holder_c::/item::/deep)": ["test.move(holder_b, holder_c)"],
        "test.destroy(holder_c::/item)": ["test.destroy(holder_c::/item::/deep)"],
        "test.destroy(holder_c)": ["test.destroy(holder_c::/item)"],
    }


def test_destroy_excludes_child_destroy_reached_through_parent_move_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.destroy(box::/item)": ["test.create(box::/item)"],
        "test.move(box, holder_a)": ["test.destroy(box::/item)"],
        "test.move(holder_a, holder_b)": ["test.move(box, holder_a)"],
        # The final parent Move already reaches the earlier child Destroy.
        "test.destroy(holder_b)": ["test.move(holder_a, holder_b)"],
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


def test_independent_child_moves_with_shared_move_chain_remain_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.move(source, stage_a)": ["test.create(source)"],
        "test.move(stage_a, stage_b)": ["test.move(source, stage_a)"],
        "test.move(stage_b, workspace)": ["test.move(stage_a, stage_b)"],
        "test.move(workspace, moved_marker)": ["test.move(stage_b, workspace)"],
        "test.create(workspace)": ["test.move(workspace, moved_marker)"],
        "test.create(workspace::/box_a)": ["test.create(workspace)"],
        "test.create(workspace::/box_a::/left)": ["test.create(workspace::/box_a)"],
        "test.create(workspace::/box_a::/right)": ["test.create(workspace::/box_a)"],
        "test.move(workspace::/box_a::/left, left_a_holder)": [
            "test.create(workspace::/box_a::/left)"
        ],
        "test.move(workspace::/box_a::/right, right_a_holder)": [
            "test.create(workspace::/box_a::/right)"
        ],
        # Neither child Move reaches the other, so the Destroy retains both even
        # though they have the same preceding Move chain.
        "test.destroy(workspace::/box_a)": [
            "test.move(workspace::/box_a::/left, left_a_holder)",
            "test.move(workspace::/box_a::/right, right_a_holder)",
        ],
        "test.destroy(left_a_holder)": [
            "test.move(workspace::/box_a::/left, left_a_holder)"
        ],
        "test.destroy(right_a_holder)": [
            "test.move(workspace::/box_a::/right, right_a_holder)"
        ],
        "test.create(workspace::/box_b)": ["test.create(workspace)"],
        "test.create(workspace::/box_b::/left)": ["test.create(workspace::/box_b)"],
        "test.create(workspace::/box_b::/right)": ["test.create(workspace::/box_b)"],
        "test.move(workspace::/box_b::/left, left_b_holder)": [
            "test.create(workspace::/box_b::/left)"
        ],
        "test.move(workspace::/box_b::/right, right_b_holder)": [
            "test.create(workspace::/box_b::/right)"
        ],
        # The second Destroy repeats the same semantic relationship on a different
        # child position path.
        "test.destroy(workspace::/box_b)": [
            "test.move(workspace::/box_b::/left, left_b_holder)",
            "test.move(workspace::/box_b::/right, right_b_holder)",
        ],
        "test.destroy(left_b_holder)": [
            "test.move(workspace::/box_b::/left, left_b_holder)"
        ],
        "test.destroy(right_b_holder)": [
            "test.move(workspace::/box_b::/right, right_b_holder)"
        ],
        "test.destroy(workspace)": [
            "test.destroy(workspace::/box_a)",
            "test.destroy(workspace::/box_b)",
        ],
        "test.destroy(moved_marker)": ["test.move(workspace, moved_marker)"],
    }
