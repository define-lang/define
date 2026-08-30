from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest

_TEST = "action<my.domain.com:my_lib:/test>"


def test_triggered_action_destroys_its_own_trigger_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_trigger_inlines_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Triggering /other includes its Create in the caller's complete
        # operation dependency graph.
        "other.create(output)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::output)": ["other.create(output)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_local_create_and_action_execution_run_in_parallel(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/other::trigger_pos)": [],
        # The two actions' unrelated local Creates remain independent.
        "other.create(other_item)": [],
        "other.destroy(other_item)": ["other.create(other_item)"],
        "test.create(local_item)": [],
        "test.destroy(local_item)": ["test.create(local_item)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_fill_of_a_child_waits_only_on_the_caller_fill_of_its_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Because the child starts empty, filling it waits on the caller's
        # Create of its parent rather than on another caller operation.
        "other.create(output::/a)": ["test.create(gateway::/other::output)"],
        "test.destroy(gateway::/other::output::/a)": ["other.create(output::/a)"],
        "test.destroy(gateway::/other::output)": [
            "test.destroy(gateway::/other::output::/a)"
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_fill_of_a_child_waits_on_the_caller_destroy_that_emptied_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output::/a)": ["test.create(gateway::/other::output)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.destroy(gateway::/other::output::/a)": ["other.create(output::/a)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        # A caller-satisfied empty requirement keeps the caller's Destroy instead
        # of falling back to the parent fill.
        "other#2.create(output::/a)": ["test.destroy(gateway::/other::output::/a)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::output::/a)#2": ["other#2.create(output::/a)"],
        "test.destroy(gateway::/other::output)": [
            "test.destroy(gateway::/other::output::/a)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_consumes_a_guarantee_the_callee_filled_by_moving_a_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The caller's Destroy of the child waits for the Move that carried the
        # particle into the guaranteed position.
        "other.move(source, holder)": ["test.create(gateway::/other::source::/a)"],
        "test.destroy(gateway::/other::holder::/a)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::holder)": [
            "test.destroy(gateway::/other::holder::/a)"
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_move_of_a_caller_filled_position_waits_on_every_child_the_caller_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::source::/b)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Moving the parent particle waits independently on both child Creates
        # performed by the caller.
        "other.move(source, holder)": [
            "test.create(gateway::/other::source::/a)",
            "test.create(gateway::/other::source::/b)",
        ],
        "test.destroy(gateway::/other::holder::/a)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::holder::/b)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::holder)": [
            "test.destroy(gateway::/other::holder::/b)",
            "test.destroy(gateway::/other::holder::/a)",
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_destroy_of_a_caller_filled_position_waits_on_the_caller_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::input)": ["test.create(gateway)"],
        "test.create(gateway::/other::input::/item)": [
            "test.create(gateway::/other::input)"
        ],
        "test.create(gateway::/other::input::/item::/deep)": [
            "test.create(gateway::/other::input::/item)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Destroying the caller-created particle waits for the deepest child
        # Create before the destruction cascade continues to its parent names.
        "other.destroy(input::/item::/deep)": [
            "test.create(gateway::/other::input::/item::/deep)"
        ],
        "other.destroy(input::/item)": ["other.destroy(input::/item::/deep)"],
        "test.destroy(gateway::/other::input)": ["other.destroy(input::/item)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_destroy_excludes_reachable_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/origin)": ["test.create(/input)"],
        "test.move(/input::/origin, holder_a)": ["test.create(/input::/origin)"],
        "test.move(holder_a, /input::/middle)": [
            "test.move(/input::/origin, holder_a)"
        ],
        "test.move(/input::/middle, /input::/target)": [
            "test.move(holder_a, /input::/middle)"
        ],
        "test.move(/input::/target, holder_c)": [
            "test.move(/input::/middle, /input::/target)"
        ],
        "test.destroy(holder_c)": ["test.move(/input::/target, holder_c)"],
        "test.create(/other::trigger_pos)": [],
        # The final caller child Move already reaches the Move that emptied origin,
        # so caller substitution excludes the earlier Move from this Destroy.
        "other.destroy(/input)": ["test.move(/input::/target, holder_c)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_move_excludes_reachable_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/origin)": ["test.create(/input)"],
        "test.move(/input::/origin, holder_a)": ["test.create(/input::/origin)"],
        "test.move(holder_a, /input::/middle)": [
            "test.move(/input::/origin, holder_a)"
        ],
        "test.move(/input::/middle, /input::/target)": [
            "test.move(holder_a, /input::/middle)"
        ],
        "test.move(/input::/target, holder_c)": [
            "test.move(/input::/middle, /input::/target)"
        ],
        "test.destroy(holder_c)": ["test.move(/input::/target, holder_c)"],
        "test.create(/other::trigger_pos)": [],
        # The final caller child Move already reaches the Move that emptied origin,
        # so caller substitution excludes the earlier Move from this Move.
        "other.move(/input, holder)": ["test.move(/input::/target, holder_c)"],
        "other.destroy(holder)": ["other.move(/input, holder)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_excludes_caller_child_move_reached_by_local_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/origin)": ["test.create(/input)"],
        "test.move(/input::/origin, /input::/start)": ["test.create(/input::/origin)"],
        "test.create(/other::trigger_pos)": [],
        "other.move(/input::/start, /input::/middle)": [
            "test.move(/input::/origin, /input::/start)"
        ],
        "other.move(/input::/middle, /input::/target)": [
            "other.move(/input::/start, /input::/middle)"
        ],
        "other.move(/input::/target, holder)": [
            "other.move(/input::/middle, /input::/target)"
        ],
        # The final local child Move reaches the caller Move through the local Move
        # chain, so the Empty Rule excludes the caller Move from this Destroy.
        "other.destroy(/input)": ["other.move(/input::/target, holder)"],
        "other.destroy(holder)": ["other.move(/input::/target, holder)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_excludes_sibling_move_depended_on_via_another_callee_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/a)": ["test.create(/input)"],
        "test.move(/input::/a, /holder)": ["test.create(/input::/a)"],
        "test.move(/holder, /intermediate)": ["test.move(/input::/a, /holder)"],
        "test.create(/other::trigger_pos)": [],
        "other.move(/intermediate, /input::/b)": [
            "test.move(/holder, /intermediate)",
        ],
        "other.move(/input::/b, sink)": ["other.move(/intermediate, /input::/b)"],
        # The remaining operation on child b depends on the caller's Move on child a
        # through the particle in the separate intermediate position.
        "other.destroy(/input)": ["other.move(/input::/b, sink)"],
        "other.destroy(sink)": ["other.move(/input::/b, sink)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_remaining_move_has_two_paths_to_one_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/a)": ["test.create(/input)"],
        "test.create(/other::trigger_pos)": [],
        "other.move(/input::/a, holder_a)": ["test.create(/input::/a)"],
        "other.move(holder_a, holder_b)": ["other.move(/input::/a, holder_a)"],
        "other.create(/input::/a)": ["other.move(/input::/a, holder_a)"],
        "other.destroy(/input::/a)": ["other.create(/input::/a)"],
        # Both dependencies reach the one caller operation that supplied the
        # original particle.
        "other.move(holder_b, /input::/a)": [
            "other.move(holder_a, holder_b)",
            "other.destroy(/input::/a)",
        ],
        "other.move(/input::/a, holder_c)": ["other.move(holder_b, /input::/a)"],
        "other.destroy(/input)": ["other.move(/input::/a, holder_c)"],
        "other.destroy(holder_c)": ["other.move(/input::/a, holder_c)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_rule_excludes_guaranteed_move_reached_through_sibling_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/a)": ["test.create(/input)"],
        "test.create(/producer::trigger_pos)": [],
        "producer.move(/input::/a, /holder)": ["test.create(/input::/a)"],
        "test.move(/holder, /intermediate)": ["producer.move(/input::/a, /holder)"],
        "test.move(/intermediate, /input::/b)": ["test.move(/holder, /intermediate)"],
        "test.destroy(/input::/b)": ["test.move(/intermediate, /input::/b)"],
        # The sibling Move reaches the guaranteed Move through the particle's
        # intermediate positions, so Move Correction excludes the guaranteed Move.
        "test.destroy(/input)": ["test.destroy(/input::/b)"],
        "test.destroy(/producer::trigger_pos)": ["test.create(/producer::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_excludes_child_create_reached_through_parent_move_chain(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/item)": ["test.create(box)"],
        "test.move(box, holder_a)": ["test.create(box::/item)"],
        "test.move(holder_a, /input)": ["test.move(box, holder_a)"],
        "test.create(/other::trigger_pos)": [],
        # The latest caller Move already reaches the earlier child Create.
        "other.move(/input, output)": ["test.move(holder_a, /input)"],
        "other.destroy(output::/item)": ["other.move(/input, output)"],
        "other.destroy(output)": ["other.destroy(output::/item)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_destroy_of_a_refilled_position_ignores_the_previous_particles_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/origin)": [],
        "test.create(/origin::/child)": ["test.create(/origin)"],
        "test.destroy(/origin::/child)": ["test.create(/origin::/child)"],
        "test.destroy(/origin)": ["test.destroy(/origin::/child)"],
        "test.create(/origin)#2": ["test.destroy(/origin)"],
        "test.create(/other::trigger_pos)": [],
        "other.destroy(/origin)": ["test.create(/origin)#2"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_move_of_a_caller_filled_position_waits_on_the_deepest_child_the_caller_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::source::/a::/deep)": [
            "test.create(gateway::/other::source::/a)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The deepest caller Create supersedes the shallower child Creates as
        # the dependency for moving their parent particle.
        "other.move(source, holder)": [
            "test.create(gateway::/other::source::/a::/deep)"
        ],
        "test.destroy(gateway::/other::holder::/a::/deep)": [
            "other.move(source, holder)"
        ],
        "test.destroy(gateway::/other::holder::/a)": [
            "test.destroy(gateway::/other::holder::/a::/deep)"
        ],
        "test.destroy(gateway::/other::holder)": [
            "test.destroy(gateway::/other::holder::/a)"
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_move_joins_its_own_child_fill_and_the_caller_fill_of_another_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(source::/b)": ["test.create(gateway::/other::source)"],
        # The Move joins the caller's Create of one child with the callee's
        # Create of the other.
        "other.move(source, holder)": [
            "other.create(source::/b)",
            "test.create(gateway::/other::source::/a)",
        ],
        "test.destroy(gateway::/other::holder::/a)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::holder::/b)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::holder)": [
            "test.destroy(gateway::/other::holder::/b)",
            "test.destroy(gateway::/other::holder::/a)",
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_operation_on_a_child_supersedes_the_caller_operation_on_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(source::/a)": ["test.create(gateway::/other::source::/a)"],
        # The callee's child Destroy supersedes the caller's earlier operation
        # as the direct dependency of the parent Move.
        "other.move(source, holder)": ["other.destroy(source::/a)"],
        "test.destroy(gateway::/other::holder)": ["other.move(source, holder)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_fill_of_a_child_does_not_wait_on_the_caller_fill_of_a_sibling_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/a)": ["test.create(gateway::/other::box)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Filling child /b depends only on its parent Create, while moving its
        # sibling /a waits on the caller's Create of /a.
        "other.create(box::/b)": ["test.create(gateway::/other::box)"],
        "other.move(box::/a, keeper)": ["test.create(gateway::/other::box::/a)"],
        "test.destroy(gateway::/other::box::/b)": ["other.create(box::/b)"],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/b)",
            "other.move(box::/a, keeper)",
        ],
        "test.destroy(gateway::/other::keeper)": ["other.move(box::/a, keeper)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_operation_waits_on_callee_output_not_later_callee_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output)": ["test.create(gateway)"],
        "other.create(late)": ["test.create(gateway)"],
        "other.destroy(late)": ["other.create(late)"],
        # Consuming output waits on the operation that filled it, not on later
        # independent operations in /other.
        "test.destroy(gateway::/other::output)": ["other.create(output)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_operation_waits_on_callee_move_output(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(trigger_pos, output)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
        "test.destroy(gateway::/other::output)": ["other.move(trigger_pos, output)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_guarantee_depends_on_interface_position_not_trigger_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::input)": ["test.create(gateway)"],
        "test.create(gateway::/worker::trigger)": ["test.create(gateway)"],
        # The guaranteed Move depends on the caller's Create of input, not on
        # the independent Create that triggered /worker.
        "worker.move(input, output)": ["test.create(gateway::/worker::input)"],
        "test.destroy(gateway::/worker::output)": ["worker.move(input, output)"],
        "test.destroy(gateway::/worker::trigger)": [
            "test.create(gateway::/worker::trigger)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_operation_waits_on_callee_destroy_output(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(output)": ["test.create(gateway::/other::output)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        # The caller's refill waits on the callee operation that emptied the
        # position.
        "test.create(gateway::/other::output)#2": ["other.destroy(output)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        "other#2.destroy(output)": ["test.create(gateway::/other::output)#2"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_the_caller_destroy_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.destroy(gateway::/other::slot)": ["other.create(slot)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        # The second callee Create waits only on the caller Destroy that satisfies
        # its empty requirement.
        "other#2.create(slot)": ["test.destroy(gateway::/other::slot)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::slot)#2": ["other#2.create(slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_waits_on_the_caller_create_that_fills_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::input)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The occupied requirement resolves to the caller operation that filled
        # input.
        "other.destroy(input)": ["test.create(gateway::/other::input)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_the_caller_move_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.move(gateway::/other::slot, sink)": ["other.create(slot)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        # The second callee Create waits only on the caller Move that satisfies its
        # empty requirement.
        "other#2.create(slot)": ["test.move(gateway::/other::slot, sink)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::slot)": ["other#2.create(slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_joins_an_in_body_source_and_a_requirement_target(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(src)": ["test.create(gateway)"],
        "other.move(src, dest)": ["other.create(src)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.destroy(gateway::/other::dest)": ["other.move(src, dest)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        "other#2.create(src)": ["test.create(gateway)"],
        # The second callee Move joins its in-body source with the caller Destroy
        # that satisfies the target's empty requirement.
        "other#2.move(src, dest)": [
            "other#2.create(src)",
            "test.destroy(gateway::/other::dest)",
        ],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::dest)#2": ["other#2.move(src, dest)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_excludes_non_action_parent_create_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/item)": ["test.create(gateway::/other::box)"],
        # The parent Create is already reachable through the more recent child Create,
        # so the Move Rule excludes it.
        "other.move(box::/item, box::/destination)": ["other.create(box::/item)"],
        "test.destroy(gateway::/other::box::/destination)": [
            "other.move(box::/item, box::/destination)"
        ],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/destination)"
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_excludes_non_action_parent_move_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(box)": [],
        "test.move(box, destination)": ["test.create(box)"],
        "test.move(destination, gateway::/other::box)": [
            "test.create(gateway)",
            "test.move(box, destination)",
        ],
        "other.create(box::/item)": ["test.move(destination, gateway::/other::box)"],
        # The caller Move is already reachable through the more recent child Create,
        # so the Move Rule excludes it through its other operated position, box.
        "other.move(box::/item, destination)": ["other.create(box::/item)"],
        "other.destroy(box)": ["other.move(box::/item, destination)"],
        "test.destroy(gateway::/other::destination)": [
            "other.move(box::/item, destination)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_child_empty_requirement_waits_on_the_caller_empty_of_the_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child)": ["test.create(gateway::/other::box)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.destroy(gateway::/other::box::/child)": ["other.create(box::/child)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        # The second child Create waits on the caller Destroy of that child, not
        # merely on the action trigger.
        "other#2.create(box::/child)": ["test.destroy(gateway::/other::box::/child)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::box::/child)#2": ["other#2.create(box::/child)"],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/child)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_by_default_child_requirements_branch_from_the_caller_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Both empty-by-default child Creates branch directly from the caller's
        # Create of their parent.
        "other.create(box::/a)": ["test.create(gateway::/other::box)"],
        "other.create(box::/b)": ["test.create(gateway::/other::box)"],
        "test.destroy(gateway::/other::box::/a)": ["other.create(box::/a)"],
        "test.destroy(gateway::/other::box::/b)": ["other.create(box::/b)"],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/b)",
            "test.destroy(gateway::/other::box::/a)",
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_grandchild_requirement_waits_on_the_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The callee's operation on the grandchild waits for the caller's Create
        # at that exact position.
        "other.destroy(box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child::/grandchild)"
        ],
        "test.destroy(gateway::/other::box::/child)": [
            "other.destroy(box::/child::/grandchild)"
        ],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/child)"
        ],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_grandchild_requirement_waits_on_the_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.destroy(gateway::/other::box::/child::/grandchild)": [
            "other.create(box::/child::/grandchild)"
        ],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        # The second grandchild Create waits on the caller Destroy at the same
        # contracted position depth.
        "other#2.create(box::/child::/grandchild)": [
            "test.destroy(gateway::/other::box::/child::/grandchild)"
        ],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
        "test.destroy(gateway::/other::box::/child::/grandchild)#2": [
            "other#2.create(box::/child::/grandchild)"
        ],
        "test.destroy(gateway::/other::box::/child)": [
            "test.destroy(gateway::/other::box::/child::/grandchild)#2"
        ],
        "test.destroy(gateway::/other::box)": [
            "test.destroy(gateway::/other::box::/child)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_emptying_a_four_level_particle_waits_only_on_the_deepest_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/parent::/child::/grandchild)": ["test.create(/parent::/child)"],
        "test.create(/parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(/parent::/child::/grandchild)"
        ],
        "test.create(/other::trigger_pos)": [],
        # Emptying the four-level particle waits only on the deepest caller
        # operation because it already follows every shallower Create.
        "other.move(/parent, out)": [
            "test.create(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "test.destroy(/other::out::/child::/grandchild::/greatgrandchild)": [
            "other.move(/parent, out)"
        ],
        "test.destroy(/other::out::/child::/grandchild)": [
            "test.destroy(/other::out::/child::/grandchild::/greatgrandchild)"
        ],
        "test.destroy(/other::out::/child)": [
            "test.destroy(/other::out::/child::/grandchild)"
        ],
        "test.destroy(/other::out)": ["test.destroy(/other::out::/child)"],
        "test.destroy(/other::trigger_pos)": ["test.create(/other::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_intermediate_callee_emptying_reaches_a_deeper_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::parent)": ["test.create(gateway)"],
        "test.create(gateway::/other::parent::/child)": [
            "test.create(gateway::/other::parent)"
        ],
        "test.create(gateway::/other::parent::/child::/grandchild)": [
            "test.create(gateway::/other::parent::/child)"
        ],
        "test.create(gateway::/other::parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(gateway::/other::parent::/child::/grandchild)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(gateway::/other::parent::/child::/grandchild::/greatgrandchild)"
        ],
        "other.destroy(parent::/child::/grandchild)": [
            "other.destroy(parent::/child::/grandchild::/greatgrandchild)"
        ],
        # Each parent Destroy follows the child Destroy that already reaches the
        # caller's deeper operation.
        "other.destroy(parent::/child)": ["other.destroy(parent::/child::/grandchild)"],
        "other.destroy(parent)": ["other.destroy(parent::/child)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_implied_position_grandchildren_wait_on_the_direct_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/inner::trigger_pos)": [],
        # Both grandchild Creates on the implied position wait directly on the
        # caller's Create of their shared parent.
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
        "test.destroy(/inner::trigger_pos)": ["test.create(/inner::trigger_pos)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_resolves_to_the_most_recent_empty_before_the_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/filler::trigger_pos)": ["test.create(gw)"],
        "filler.create(slot)": ["test.create(gw)"],
        "filler.destroy(trigger_pos)": ["test.create(gw::/filler::trigger_pos)"],
        "test.destroy(gw::/filler::slot)": ["filler.create(slot)"],
        "test.create(gw::/filler::trigger_pos)#2": ["filler.destroy(trigger_pos)"],
        "filler#2.create(slot)": ["test.destroy(gw::/filler::slot)"],
        "filler#2.destroy(trigger_pos)": ["test.create(gw::/filler::trigger_pos)#2"],
        "test.destroy(gw::/filler::slot)#2": ["filler#2.create(slot)"],
        "test.create(gw::/filler::trigger_pos)#3": ["filler#2.destroy(trigger_pos)"],
        # The third callee Create resolves to the second, most recent caller
        # Destroy, rather than the stale first Destroy.
        "filler#3.create(slot)": ["test.destroy(gw::/filler::slot)#2"],
        "filler#3.destroy(trigger_pos)": ["test.create(gw::/filler::trigger_pos)#3"],
        "test.destroy(gw::/filler::slot)#3": ["filler#3.create(slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_resolves_to_the_constraint_satisfying_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(action_holder)": [],
        "test.create(box1)": [],
        "test.create(box2)": [],
        "test.move(box2, action_holder::/move::input)": [
            "test.create(action_holder)",
            "test.create(box2)",
        ],
        "move.move(input, output)": ["test.move(box2, action_holder::/move::input)"],
        "test.move(action_holder::/move::output, box2)": ["move.move(input, output)"],
        "test.move(box1, action_holder::/move::input)": [
            "test.create(box1)",
            "move.move(input, output)",
        ],
        # The second action Move waits on the box1 fill—the most recent fill of
        # input—and on the caller Move that emptied output after the first call.
        "move#2.move(input, output)": [
            "test.move(action_holder::/move::output, box2)",
            "test.move(box1, action_holder::/move::input)",
        ],
        "test.move(action_holder::/move::output, dest)": ["move#2.move(input, output)"],
        "test.create(dest::/a)": ["test.move(action_holder::/move::output, dest)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_trigger_position_read_keeps_the_trigger_edge_when_a_requirement_resolves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        "worker.move(in, out)": ["test.create(gw::/worker::in)"],
        "test.destroy(gw::/worker::out)": ["worker.move(in, out)"],
        "test.create(gw::/worker::in)#2": ["worker.move(in, out)"],
        # The second Move reads the trigger position while its empty requirement
        # resolves to the caller Destroy, so neither dependency may displace the
        # other.
        "worker#2.move(in, out)": [
            "test.destroy(gw::/worker::out)",
            "test.create(gw::/worker::in)#2",
        ],
        "test.destroy(gw::/worker::out)#2": ["worker#2.move(in, out)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_trigger_position_read_keeps_the_trigger_edge_when_an_occupied_requirement_resolves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/worker::box)": ["test.create(gw)"],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        # The Move keeps both its trigger-position dependency and the caller
        # operation that satisfies its occupied requirement.
        "worker.move(in, box::/y)": [
            "test.create(gw::/worker::box)",
            "test.create(gw::/worker::in)",
        ],
        "test.destroy(gw::/worker::box::/y)": ["worker.move(in, box::/y)"],
        "test.destroy(gw::/worker::box)": ["test.destroy(gw::/worker::box::/y)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_triggered_action_with_no_guarantees_still_runs(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/worker::trigger_pos)": ["test.create(gw)"],
        # The worker's local operations remain in the complete graph even though
        # it guarantees no contracted position.
        "worker.create(scratch)": ["test.create(gw)"],
        "worker.destroy(scratch)": ["worker.create(scratch)"],
        "test.create(note)": [],
        "test.destroy(gw::/worker::trigger_pos)": [
            "test.create(gw::/worker::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_two_interface_positions_bound_by_caller(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/caller::run)": [],
        "caller.create(first_gateway)": [],
        "caller.create(first_gateway::/worker::second)": [
            "caller.create(first_gateway)"
        ],
        "caller.create(first_gateway::/worker::third)": [
            "caller.create(first_gateway)"
        ],
        "caller.create(first_gateway::/worker::first)": [
            "caller.create(first_gateway)"
        ],
        # The caller binds both interface positions, so each Destroy depends on
        # the corresponding caller Create.
        "worker.destroy(second)": ["caller.create(first_gateway::/worker::second)"],
        "worker.destroy(third)": ["caller.create(first_gateway::/worker::third)"],
        "caller.create(second_gateway)": [],
        "caller.create(second_gateway::/worker::second)": [
            "caller.create(second_gateway)"
        ],
        "caller.create(second_gateway::/worker::third)": [
            "caller.create(second_gateway)"
        ],
        "caller.create(second_gateway::/worker::first)": [
            "caller.create(second_gateway)"
        ],
        # The second worker execution resolves the same two dependencies
        # independently.
        "worker#2.destroy(second)": ["caller.create(second_gateway::/worker::second)"],
        "worker#2.destroy(third)": ["caller.create(second_gateway::/worker::third)"],
        "caller.destroy(first_gateway::/worker::first)": [
            "caller.create(first_gateway::/worker::first)"
        ],
        "caller.destroy(first_gateway)": [
            "caller.destroy(first_gateway::/worker::first)",
            "worker.destroy(second)",
            "worker.destroy(third)",
        ],
        "caller.destroy(second_gateway::/worker::first)": [
            "caller.create(second_gateway::/worker::first)"
        ],
        "caller.destroy(second_gateway)": [
            "caller.destroy(second_gateway::/worker::first)",
            "worker#2.destroy(second)",
            "worker#2.destroy(third)",
        ],
        "caller.destroy(run)": ["test.create(/caller::run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_parallel_callee_local_operation_chains_wait_on_action_parent_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::trigger_pos)": ["test.create(gateway)"],
        # The callee's two local operation chains are independent after their
        # shared parent operation.
        "worker.create(first)": ["test.create(gateway)"],
        "worker.destroy(first)": ["worker.create(first)"],
        "worker.create(second)": ["test.create(gateway)"],
        "worker.destroy(second)": ["worker.create(second)"],
        "test.destroy(gateway::/worker::trigger_pos)": [
            "test.create(gateway::/worker::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_trigger_inlines_callee_internal_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # Triggering /other preserves both its serial scratch chain and its
        # independent output Create in the complete graph.
        "other.create(scratch)": ["test.create(gateway)"],
        "other.destroy(scratch)": ["other.create(scratch)"],
        "other.create(output)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::output)": ["other.create(output)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_known_child_and_caller_unknown_sibling_are_disjoint(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": [
            "test.create(source::/child)",
            "test.create(source::/sibling)",
        ],
        "test.create(/destroyer::trigger_pos)": [],
        # The caller-only sibling Destroy and the callee's first Move of /child
        # both depend on the Move that supplied the parent particle. Neither
        # operation depends on the other.
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(parent::/child, keeper)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(keeper, parent::/child)": [
            "destroyer.move(parent::/child, keeper)"
        ],
        "destroyer.destroy(parent::/child)": ["destroyer.move(keeper, parent::/child)"],
        # The parent Destroy waits for both independently ordered child Destroys.
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "destroyer.destroy(parent::/child)",
        ],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_only_child_assigned_before_callee_known_child_is_disjoint(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": [
            "test.create(source::/sibling)",
            "test.create(source::/child)",
        ],
        "test.create(/destroyer::trigger_pos)": [],
        # Assigning the caller-only sibling before the callee-known child does not
        # add a dependency between the sibling Destroy and the first Move of the
        # child particle.
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(parent::/child, keeper)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.move(keeper, parent::/child)": [
            "destroyer.move(parent::/child, keeper)"
        ],
        "destroyer.destroy(parent::/child)": ["destroyer.move(keeper, parent::/child)"],
        # The parent Destroy still waits for both child Destroys.
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "destroyer.destroy(parent::/child)",
        ],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_local_cascade_uses_caller_fragment_for_occupied_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.move(source, /triggered::run)": ["test.create(source::/a)"],
        "triggered.move(run, /target)": ["test.move(source, /triggered::run)"],
        "triggered.move(/target, local)": ["triggered.move(run, /target)"],
        # The contributed child Destroy follows the particle across both Moves
        # and must finish before the local-position Destroy.
        "triggered.destroy(local::/a)": ["triggered.move(/target, local)"],
        "triggered.destroy(local)": ["triggered.destroy(local::/a)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_auto_destruction_uses_caller_fragment_for_occupied_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.move(source, /triggered::run)": ["test.create(source::/a)"],
        "triggered.move(run, /target)": ["test.move(source, /triggered::run)"],
        "triggered.move(/target, local)": ["triggered.move(run, /target)"],
        # The caller-only child must be destroyed before the callee's local
        # position is automatically destroyed.
        "triggered.destroy(local::/a)": ["triggered.move(/target, local)"],
        "triggered.destroy(local)": ["triggered.destroy(local::/a)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_contributed_child_destruction_precedes_later_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(child_particle)": [],
        "test.create(child_particle::/child)": ["test.create(child_particle)"],
        "test.move(child_particle, source::/run)": [
            "test.create(source)",
            "test.create(child_particle::/child)",
        ],
        "test.move(source, /destroyer::run)": [
            "test.move(child_particle, source::/run)"
        ],
        "destroyer.destroy(run::/run::/child)": ["test.move(source, /destroyer::run)"],
        "destroyer.destroy(run::/run)": ["destroyer.destroy(run::/run::/child)"],
        # The caller-contributed child Destroy must remain before the later parent
        # Destroy recorded after the contracted particle's destruction cascade.
        "destroyer.destroy(run)": ["destroyer.destroy(run::/run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_contributes_one_destroy_before_shared_callee_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::parent)": ["test.create(gateway)"],
        "test.create(gateway::/other::parent::/child)": [
            "test.create(gateway::/other::parent)"
        ],
        "test.create(gateway::/other::parent::/child::/sibling)": [
            "test.create(gateway::/other::parent::/child)"
        ],
        "test.create(gateway::/other::parent::/child::/grandchild)": [
            "test.create(gateway::/other::parent::/child)"
        ],
        "test.create(gateway::/other::parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(gateway::/other::parent::/child::/grandchild)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The caller contributes the sibling Destroy, which follows the caller's
        # Create of that sibling particle.
        "other.destroy(parent::/child::/sibling)": [
            "test.create(gateway::/other::parent::/child::/sibling)",
        ],
        # The grandchild contract has a distinct Destruction Fact, so the child
        # contract independently contributes the caller-known greatgrandchild.
        "other.destroy(parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(gateway::/other::parent::/child::/grandchild::/greatgrandchild)"
        ],
        # The explicit grandchild Destroy waits for the contribution belonging to
        # its distinct Destruction Fact.
        "other.destroy(parent::/child::/grandchild)": [
            "other.destroy(parent::/child::/grandchild::/greatgrandchild)",
        ],
        # The callee-known child Destroy waits for both the caller-contributed
        # sibling Destroy and the callee's grandchild Destroy.
        "other.destroy(parent::/child)": [
            "other.destroy(parent::/child::/sibling)",
            "other.destroy(parent::/child::/grandchild)",
        ],
        # The parent Destroy waits for that shared child Destroy once.
        "other.destroy(parent)": ["other.destroy(parent::/child)"],
        "test.destroy(gateway::/other::trigger_pos)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_contributions_share_a_parent_destroy_before_callee_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/branch)": ["test.create(source)"],
        "test.create(source::/branch::/a)": ["test.create(source::/branch)"],
        "test.create(source::/branch::/b)": ["test.create(source::/branch)"],
        "test.move(source, /destroyer::parent)": [
            "test.create(source::/branch::/a)",
            "test.create(source::/branch::/b)",
        ],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.destroy(parent::/branch::/b)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent::/branch::/a)": [
            "test.move(source, /destroyer::parent)"
        ],
        # The separately begun contributions share this caller-contributed
        # parent-position Destroy before the callee destroys parent.
        "destroyer.destroy(parent::/branch)": [
            "destroyer.destroy(parent::/branch::/a)",
            "destroyer.destroy(parent::/branch::/b)",
        ],
        # The callee's parent Destroy waits on the shared caller-contributed
        # branch Destroy.
        "destroyer.destroy(parent)": ["destroyer.destroy(parent::/branch)"],
        "test.destroy(/destroyer::trigger_pos)": [
            "test.create(/destroyer::trigger_pos)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
