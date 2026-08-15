import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_CALLER_EMPTY_RULE_RETAINS_REACHABLE_DISJOINT_CHILD_DEPENDENCY = (
    "Caller Empty Rule substitution retains a child dependency already reachable "
    "through a later operation on a disjoint child position"
)


def test_triggered_action_destroys_its_own_trigger_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
    }


def test_trigger_inlines_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output)": ["test.create(gateway)"],
    }


def test_local_create_and_action_execution_run_in_parallel(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/other::trigger_pos)": [],
        "other.create(other_item)": [],
        "other.destroy(other_item)": ["other.create(other_item)"],
        "test.create(local_item)": [],
        "test.destroy(local_item)": ["test.create(local_item)"],
    }


def test_callee_fill_of_a_child_waits_only_on_the_caller_fill_of_its_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output::/a)": ["test.create(gateway::/other::output)"],
    }


def test_callee_fill_of_a_child_waits_on_the_caller_destroy_that_emptied_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::output::/a)": [
            "test.create(gateway::/other::output)"
        ],
        "test.destroy(gateway::/other::output::/a)": [
            "test.create(gateway::/other::output::/a)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output::/a)": ["test.destroy(gateway::/other::output::/a)"],
    }


def test_caller_consumes_a_guarantee_the_callee_filled_by_moving_a_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(source, holder)": ["test.create(gateway::/other::source::/a)"],
        "test.destroy(gateway::/other::holder::/a)": ["other.move(source, holder)"],
    }


def test_callee_move_of_a_caller_filled_position_waits_on_every_child_the_caller_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::source::/b)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(source, holder)": [
            "test.create(gateway::/other::source::/a)",
            "test.create(gateway::/other::source::/b)",
        ],
    }


def test_callee_destroy_of_a_caller_filled_position_waits_on_the_caller_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::input)": ["test.create(gateway)"],
        "test.create(gateway::/other::input::/item)": [
            "test.create(gateway::/other::input)"
        ],
        "test.create(gateway::/other::input::/item::/deep)": [
            "test.create(gateway::/other::input::/item)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(input::/item::/deep)": [
            "test.create(gateway::/other::input::/item::/deep)"
        ],
        "other.destroy(input::/item)": ["other.destroy(input::/item::/deep)"],
    }


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_EMPTY_RULE_RETAINS_REACHABLE_DISJOINT_CHILD_DEPENDENCY,
)
def test_caller_empty_rule_destroy_excludes_reachable_disjoint_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_EMPTY_RULE_RETAINS_REACHABLE_DISJOINT_CHILD_DEPENDENCY,
)
def test_caller_empty_rule_move_excludes_reachable_disjoint_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }


@pytest.mark.xfail(
    strict=True,
    reason=_CALLER_EMPTY_RULE_RETAINS_REACHABLE_DISJOINT_CHILD_DEPENDENCY,
)
def test_caller_empty_rule_excludes_caller_child_move_reached_by_local_child_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }


def test_callee_destroy_of_a_refilled_position_ignores_the_previous_particles_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/origin)": [],
        "test.create(/origin::/child)": ["test.create(/origin)"],
        "test.destroy(/origin::/child)": ["test.create(/origin::/child)"],
        "test.destroy(/origin)": ["test.destroy(/origin::/child)"],
        "test.create(/origin)#2": ["test.destroy(/origin)"],
        "test.create(/other::trigger_pos)": [],
        "other.destroy(/origin)": ["test.create(/origin)#2"],
    }


def test_callee_move_of_a_caller_filled_position_waits_on_the_deepest_child_the_caller_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::source::/a::/deep)": [
            "test.create(gateway::/other::source::/a)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(source, holder)": [
            "test.create(gateway::/other::source::/a::/deep)"
        ],
    }


def test_callee_move_joins_its_own_child_fill_and_the_caller_fill_of_another_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(source::/b)": ["test.create(gateway::/other::source)"],
        "other.move(source, holder)": [
            "other.create(source::/b)",
            "test.create(gateway::/other::source::/a)",
        ],
    }


def test_callee_operation_on_a_child_supersedes_the_caller_operation_on_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::source)": ["test.create(gateway)"],
        "test.create(gateway::/other::source::/a)": [
            "test.create(gateway::/other::source)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(source::/a)": ["test.create(gateway::/other::source::/a)"],
        "other.move(source, holder)": ["other.destroy(source::/a)"],
    }


def test_callee_fill_of_a_child_does_not_wait_on_the_caller_fill_of_a_sibling_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/a)": ["test.create(gateway::/other::box)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/b)": ["test.create(gateway::/other::box)"],
        "other.move(box::/a, keeper)": ["test.create(gateway::/other::box::/a)"],
    }


def test_caller_operation_waits_on_callee_output_not_later_callee_operations(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(output)": ["test.create(gateway)"],
        "other.create(late)": ["test.create(gateway)"],
        "other.destroy(late)": ["other.create(late)"],
        "test.destroy(gateway::/other::output)": ["other.create(output)"],
    }


def test_caller_operation_waits_on_callee_move_output(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.move(trigger_pos, output)": [
            "test.create(gateway::/other::trigger_pos)"
        ],
        "test.destroy(gateway::/other::output)": ["other.move(trigger_pos, output)"],
    }


def test_caller_operation_waits_on_callee_destroy_output(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::output)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(output)": ["test.create(gateway::/other::output)"],
        "test.create(gateway::/other::output)#2": ["other.destroy(output)"],
    }


def test_empty_requirement_waits_on_the_caller_destroy_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::slot)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::slot)": ["test.create(gateway::/other::slot)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.destroy(gateway::/other::slot)"],
    }


def test_occupied_requirement_waits_on_the_caller_create_that_fills_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::input)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(input)": ["test.create(gateway::/other::input)"],
    }


def test_empty_requirement_waits_on_the_caller_move_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::slot)": ["test.create(gateway)"],
        "test.move(gateway::/other::slot, sink)": [
            "test.create(gateway::/other::slot)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(slot)": ["test.move(gateway::/other::slot, sink)"],
    }


def test_move_joins_an_in_body_source_and_a_requirement_target(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::dest)": ["test.create(gateway)"],
        "test.destroy(gateway::/other::dest)": ["test.create(gateway::/other::dest)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(src)": ["test.create(gateway)"],
        "other.move(src, dest)": [
            "other.create(src)",
            "test.destroy(gateway::/other::dest)",
        ],
    }


def test_move_excludes_non_action_parent_create_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/item)": ["test.create(gateway::/other::box)"],
        # The parent Create is already reachable through the more recent child Create,
        # so the Move Rule excludes it.
        "other.move(box::/item, box::/destination)": ["other.create(box::/item)"],
    }


def test_move_excludes_non_action_parent_move_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.move(gateway::/other::box, gateway::/other::destination)": [
            "test.create(gateway::/other::box)"
        ],
        "test.move(gateway::/other::destination, gateway::/other::box)": [
            "test.move(gateway::/other::box, gateway::/other::destination)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/item)": [
            "test.move(gateway::/other::destination, gateway::/other::box)"
        ],
        # The caller Move is already reachable through the more recent child Create, so
        # the Move Rule excludes it through its other operated position, box.
        "other.move(box::/item, destination)": ["other.create(box::/item)"],
    }


def test_child_empty_requirement_waits_on_the_caller_empty_of_the_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.destroy(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child)": ["test.destroy(gateway::/other::box::/child)"],
    }


def test_empty_by_default_child_requirements_branch_from_the_caller_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/a)": ["test.create(gateway::/other::box)"],
        "other.create(box::/b)": ["test.create(gateway::/other::box)"],
    }


def test_occupied_grandchild_requirement_waits_on_the_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child::/grandchild)"
        ],
    }


def test_empty_grandchild_requirement_waits_on_the_caller_empty(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::box)": ["test.create(gateway)"],
        "test.create(gateway::/other::box::/child)": [
            "test.create(gateway::/other::box)"
        ],
        "test.create(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child)"
        ],
        "test.destroy(gateway::/other::box::/child::/grandchild)": [
            "test.create(gateway::/other::box::/child::/grandchild)"
        ],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(box::/child::/grandchild)": [
            "test.destroy(gateway::/other::box::/child::/grandchild)"
        ],
    }


def test_emptying_a_four_level_particle_waits_only_on_the_deepest_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/parent::/child::/grandchild)": ["test.create(/parent::/child)"],
        "test.create(/parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(/parent::/child::/grandchild)"
        ],
        "test.create(/other::trigger_pos)": [],
        "other.move(/parent, out)": [
            "test.create(/parent::/child::/grandchild::/greatgrandchild)"
        ],
    }


def test_intermediate_callee_emptying_reaches_a_deeper_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "other.destroy(parent::/child)": ["other.destroy(parent::/child::/grandchild)"],
        "other.destroy(parent)": ["other.destroy(parent::/child)"],
    }


def test_implied_position_grandchildren_wait_on_the_direct_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }


def test_empty_requirement_resolves_to_the_most_recent_empty_before_the_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/filler::slot)": ["test.create(gw)"],
        "test.destroy(gw::/filler::slot)": ["test.create(gw::/filler::slot)"],
        "test.create(gw::/filler::slot)#2": ["test.destroy(gw::/filler::slot)"],
        "test.destroy(gw::/filler::slot)#2": ["test.create(gw::/filler::slot)#2"],
        "test.create(gw::/filler::trigger_pos)": ["test.create(gw)"],
        "filler.create(slot)": ["test.destroy(gw::/filler::slot)#2"],
    }


def test_occupied_requirement_resolves_to_the_constraint_satisfying_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(action_holder)": [],
        "test.create(box1)": [],
        "test.create(box2)": [],
        "test.move(box2, action_holder::/move::input)": [
            "test.create(action_holder)",
            "test.create(box2)",
        ],
        "test.move(action_holder::/move::input, box2)": [
            "test.move(box2, action_holder::/move::input)"
        ],
        "test.move(box1, action_holder::/move::input)": [
            "test.create(box1)",
            "test.move(action_holder::/move::input, box2)",
        ],
        "test.create(action_holder::/move::run)": ["test.create(action_holder)"],
        "move.move(input, output)": ["test.move(box1, action_holder::/move::input)"],
        "test.move(action_holder::/move::output, dest)": ["move.move(input, output)"],
        "test.create(dest::/a)": ["test.move(action_holder::/move::output, dest)"],
    }


def test_trigger_position_read_keeps_the_trigger_edge_when_a_requirement_resolves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::out)": ["test.create(gw)"],
        "test.destroy(gw::/worker::out)": ["test.create(gw::/worker::out)"],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        "worker.move(in, out)": [
            "test.destroy(gw::/worker::out)",
            "test.create(gw::/worker::in)",
        ],
    }


def test_trigger_position_read_keeps_the_trigger_edge_when_an_occupied_requirement_resolves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::box)": ["test.create(gw)"],
        "test.create(gw::/worker::in)": ["test.create(gw)"],
        "worker.move(in, box::/y)": [
            "test.create(gw::/worker::box)",
            "test.create(gw::/worker::in)",
        ],
    }


def test_triggered_action_with_no_guarantees_still_runs(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/worker::trigger_pos)": ["test.create(gw)"],
        "worker.create(scratch)": ["test.create(gw)"],
        "worker.destroy(scratch)": ["worker.create(scratch)"],
        "test.create(note)": [],
    }


def test_triggered_action_input_releases_two_parallel_local_operation_chains(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::trigger_pos)": ["test.create(gateway)"],
        "worker.create(first)": ["test.create(gateway)"],
        "worker.destroy(first)": ["worker.create(first)"],
        "worker.create(second)": ["test.create(gateway)"],
        "worker.destroy(second)": ["worker.create(second)"],
    }


def test_trigger_inlines_callee_internal_dependencies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.create(scratch)": ["test.create(gateway)"],
        "other.destroy(scratch)": ["other.create(scratch)"],
        "other.create(output)": ["test.create(gateway)"],
    }


def test_callee_known_child_and_caller_unknown_sibling_are_disjoint(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }


def test_caller_only_child_assigned_before_callee_known_child_is_disjoint(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }


def test_local_cascade_uses_caller_fragment_for_occupied_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_auto_destruction_uses_caller_fragment_for_occupied_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_caller_contributed_child_destruction_precedes_later_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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


def test_caller_contributes_one_destroy_before_shared_callee_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        # The caller contributes the sibling Destroy, which follows the caller's
        # Create of that sibling particle.
        "other.destroy(parent::/child::/sibling)": [
            "test.create(gateway::/other::parent::/child::/sibling)",
        ],
        # The callee's explicit grandchild Destroy retains its ordinary dependency.
        "other.destroy(parent::/child::/grandchild)": [
            "test.create(gateway::/other::parent::/child::/grandchild)"
        ],
        # The callee-known child Destroy waits for both the caller-contributed
        # sibling Destroy and the callee's grandchild Destroy.
        "other.destroy(parent::/child)": [
            "other.destroy(parent::/child::/sibling)",
            "other.destroy(parent::/child::/grandchild)",
        ],
        # The parent Destroy waits for that shared child Destroy once.
        "other.destroy(parent)": ["other.destroy(parent::/child)"],
    }


def test_caller_contributions_share_a_parent_destroy_before_callee_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
    }
