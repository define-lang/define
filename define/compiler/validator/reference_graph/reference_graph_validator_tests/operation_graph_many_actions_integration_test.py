import pytest

from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_CALLER_DEPENDENT_DESTRUCTION_CHILDREN_MISSING = (
    "destroying actions do not yet include caller-dependent child positions"
)


def test_caller_input_feeds_local_fragment_and_multiple_triggered_inputs(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/shared)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/shared::/marker)": ["test.create(/shared)"],
        "middle.create(/shared::/child_a::trigger_pos)": ["test.create(/shared)"],
        "middle.create(/shared::/child_b::trigger_pos)": ["test.create(/shared)"],
        "child_a.create(scratch)": ["test.create(/shared)"],
        "child_a.destroy(scratch)": ["child_a.create(scratch)"],
        "child_b.create(scratch)": ["test.create(/shared)"],
        "child_b.destroy(scratch)": ["child_b.create(scratch)"],
    }


def test_two_child_actions_trigger_in_parallel(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/first::trigger_pos)": ["test.create(box)"],
        "test.create(box::/second::trigger_pos)": ["test.create(box)"],
        "first.destroy(trigger_pos)": ["test.create(box::/first::trigger_pos)"],
        "second.destroy(trigger_pos)": ["test.create(box::/second::trigger_pos)"],
        "test.destroy(box)": [
            "first.destroy(trigger_pos)",
            "second.destroy(trigger_pos)",
        ],
    }


def test_action_trigger_and_empty_rule_use_the_same_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::source)": ["test.create(gateway)"],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.create(source::/child::trigger_pos)": [
            "test.create(gateway::/middle::source)"
        ],
        "child.create(scratch)": ["test.create(gateway::/middle::source)"],
        "child.destroy(scratch)": ["child.create(scratch)"],
        "middle.move(source, holder)": ["middle.create(source::/child::trigger_pos)"],
    }


def test_empty_rule_adds_a_caller_child_operation_to_a_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::source)": ["test.create(gateway)"],
        "test.create(gateway::/middle::source::/marker)": [
            "test.create(gateway::/middle::source)"
        ],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.create(source::/child::trigger_pos)": [
            "test.create(gateway::/middle::source)"
        ],
        "child.create(scratch)": ["test.create(gateway::/middle::source)"],
        "child.destroy(scratch)": ["child.create(scratch)"],
        "middle.move(source, holder)": [
            "middle.create(source::/child::trigger_pos)",
            "test.create(gateway::/middle::source::/marker)",
        ],
    }


def test_caller_consumes_a_child_guarantee_after_an_empty_rule_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::source)": ["test.create(gateway)"],
        "test.create(gateway::/middle::source::/marker)": [
            "test.create(gateway::/middle::source)"
        ],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.create(source::/child::trigger_pos)": [
            "test.create(gateway::/middle::source)"
        ],
        "child.create(result)": ["test.create(gateway::/middle::source)"],
        "middle.move(source, holder)": [
            "middle.create(source::/child::trigger_pos)",
            "child.create(result)",
            "test.create(gateway::/middle::source::/marker)",
        ],
        "test.move(gateway::/middle::holder::/child::result, result)": [
            "middle.move(source, holder)"
        ],
    }


def test_child_guarantee_with_distinct_occupied_and_empty_rule_inputs(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::source)": ["test.create(gateway)"],
        "test.create(gateway::/middle::source::/marker)": [
            "test.create(gateway::/middle::source)"
        ],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.create(source::/child::trigger_pos)": [
            "test.create(gateway::/middle::source)"
        ],
        "child.create(scratch)": ["test.create(gateway::/middle::source)"],
        "child.destroy(scratch)": ["child.create(scratch)"],
        "child.create(result)": ["test.create(gateway::/middle::source)"],
        "middle.move(source, holder)": [
            "middle.create(source::/child::trigger_pos)",
            "child.create(result)",
            "test.create(gateway::/middle::source::/marker)",
        ],
        "test.move(gateway::/middle::holder::/child::result, result)": [
            "middle.move(source, holder)"
        ],
    }


def test_actions_with_identically_named_child_actions_have_distinct_instances(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/first::trigger_pos)": [],
        "test.create(/second::trigger_pos)": [],
        "first.create(box)": [],
        "first.create(box::/inner::trigger_pos)": ["first.create(box)"],
        "first.destroy(box::/inner::trigger_pos)": [
            "first.create(box::/inner::trigger_pos)"
        ],
        "first.destroy(box)": ["first.destroy(box::/inner::trigger_pos)"],
        "second.create(box)": [],
        "second.create(box::/inner::trigger_pos)": ["second.create(box)"],
        "second.destroy(box::/inner::trigger_pos)": [
            "second.create(box::/inner::trigger_pos)"
        ],
        "second.destroy(box)": ["second.destroy(box::/inner::trigger_pos)"],
        "first:inner.create(scratch)": ["first.create(box)"],
        "first:inner.destroy(scratch)": ["first:inner.create(scratch)"],
        "second:inner.create(scratch)": ["second.create(box)"],
        "second:inner.destroy(scratch)": ["second:inner.create(scratch)"],
    }


def test_occupied_requirement_two_levels_up_waits_on_the_caller_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::slot)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.destroy(slot)": ["test.create(box::/middle::gw::/inner::slot)"],
    }


def test_occupied_requirement_two_levels_up_waits_on_the_caller_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.move(source, box::/middle::gw::/inner::slot)": [
            "test.create(source)",
            "test.create(box::/middle::gw)",
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.destroy(slot)": ["test.move(source, box::/middle::gw::/inner::slot)"],
    }


def test_empty_rule_propagates_an_intermediate_move_on_a_child_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/input)": [],
        "test.create(/destination)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.move(/destination, /input::/marker)": [
            "test.create(/input)",
            "test.create(/destination)",
        ],
        "middle.create(/inner::trigger_pos)": [],
        "inner.move(/input, /destination)": [
            "middle.move(/destination, /input::/marker)"
        ],
    }


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::slot)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.destroy(gw::/inner::slot)": [
            "test.create(box::/middle::gw::/inner::slot)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(slot)": ["middle.destroy(gw::/inner::slot)"],
    }


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_interface_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::holder)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/middle::gw::/inner::holder)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.destroy(gw::/inner::holder::/a)": [
            "test.create(box::/middle::gw::/inner::holder::/a)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(holder::/a)": ["middle.destroy(gw::/inner::holder::/a)"],
    }


def test_empty_by_default_interface_child_waits_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::holder)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(holder::/a)": ["test.create(box::/middle::gw::/inner::holder)"],
    }


def test_empty_requirement_waits_on_a_destroy_by_a_caller_that_does_not_trigger_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::mw)": ["test.create(box)"],
        "test.create(box::/outer::mw::/middle::gw)": ["test.create(box::/outer::mw)"],
        "test.create(box::/outer::mw::/middle::gw::/inner::slot)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.destroy(mw::/middle::gw::/inner::slot)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::slot)"
        ],
        "outer.create(mw::/middle::trigger_pos)": ["test.create(box::/outer::mw)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "inner.create(slot)": ["outer.destroy(mw::/middle::gw::/inner::slot)"],
    }


def test_empty_requirement_waits_on_an_interface_child_destroy_by_a_caller_that_does_not_trigger_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::mw)": ["test.create(box)"],
        "test.create(box::/outer::mw::/middle::gw)": ["test.create(box::/outer::mw)"],
        "test.create(box::/outer::mw::/middle::gw::/inner::holder)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "test.create(box::/outer::mw::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::holder)"
        ],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.destroy(mw::/middle::gw::/inner::holder::/a)": [
            "test.create(box::/outer::mw::/middle::gw::/inner::holder::/a)"
        ],
        "outer.create(mw::/middle::trigger_pos)": ["test.create(box::/outer::mw)"],
        "middle.create(gw::/inner::trigger_pos)": [
            "test.create(box::/outer::mw::/middle::gw)"
        ],
        "inner.create(holder::/a)": [
            "outer.destroy(mw::/middle::gw::/inner::holder::/a)"
        ],
    }


def test_move_excludes_parent_dependency_when_source_dependency_is_a_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/box)": [],
        "test.create(/box::/producer::input)": ["test.create(/box)"],
        "producer.move(input, result)": ["test.create(/box::/producer::input)"],
        "test.move(/box::/producer::result, /box::/destination)": [
            "producer.move(input, result)"
        ],
    }


def test_callee_operation_without_position_dependencies_waits_on_action_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/box)": [],
        "test.create(/box::/worker::trigger_pos)": ["test.create(/box)"],
        "worker.create(result)": ["test.create(/box)"],
    }


def test_destroy_excludes_callee_operations_superseded_on_child_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/worker::input)": ["test.create(box)"],
        "worker.move(input, result)": ["test.create(box::/worker::input)"],
        "test.destroy(box::/worker::result)": ["worker.move(input, result)"],
        "test.destroy(box)": ["test.destroy(box::/worker::result)"],
    }


def test_espresso_operation_graph(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(station)": [],
        "test.create(station::/grind::beans)": ["test.create(station)"],
        "test.create(station::/heat::cold_water)": ["test.create(station)"],
        "grind.move(beans, grounds)": ["test.create(station::/grind::beans)"],
        "heat.move(cold_water, hot_water)": ["test.create(station::/heat::cold_water)"],
        "test.move(station::/grind::grounds, station::/brew::grounds)": [
            "grind.move(beans, grounds)"
        ],
        "test.move(station::/heat::hot_water, station::/brew::water)": [
            "heat.move(cold_water, hot_water)"
        ],
        "brew.create(cup)": ["test.create(station)"],
        "brew.destroy(water)": [
            "test.move(station::/heat::hot_water, station::/brew::water)"
        ],
        "brew.move(grounds, spent_puck)": [
            "test.move(station::/grind::grounds, station::/brew::grounds)"
        ],
        "test.destroy(station::/brew::cup)": ["brew.create(cup)"],
        "test.destroy(station::/brew::spent_puck)": ["brew.move(grounds, spent_puck)"],
        "test.destroy(station)": [
            "test.destroy(station::/brew::cup)",
            "test.destroy(station::/brew::spent_puck)",
            "brew.destroy(water)",
        ],
    }


def test_implied_position_children_wait_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child1)": ["test.create(/parent)"],
        "inner.create(/parent::/child2)": ["test.create(/parent)"],
    }


def test_implied_action_inherits_the_current_actions_parent_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(local)": [],
        "test.create(local::/parent)": ["test.create(local)"],
        "test.create(local::/parent::/middle::trigger_pos)": [
            "test.create(local::/parent)"
        ],
        "middle.create(/inner::trigger_pos)": ["test.create(local::/parent)"],
        "inner.create(scratch)": ["test.create(local::/parent)"],
        "inner.destroy(scratch)": ["inner.create(scratch)"],
    }


def test_implied_position_grandchildren_wait_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }


def test_intermediate_callee_operation_suppresses_only_its_caller_path(
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
        "test.create(/parent::/sibling)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.destroy_if_occupied(/parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "middle.destroy(/parent::/child::/grandchild)": [
            "middle.destroy_if_occupied(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "middle.create(/inner::trigger_pos)": [],
        "inner.destroy_if_occupied(/parent::/sibling)": [
            "test.create(/parent::/sibling)"
        ],
        "inner.destroy_if_occupied(/parent::/child)": [
            "middle.destroy(/parent::/child::/grandchild)",
        ],
        "inner.destroy(/parent)": [
            "inner.destroy_if_occupied(/parent::/sibling)",
            "inner.destroy_if_occupied(/parent::/child)",
        ],
    }


def test_moved_in_parent_children_branch_from_the_carrying_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(mw)": [],
        "test.create(mw::/middle::iface)": ["test.create(mw)"],
        "test.create(mw::/middle::iface::/parent)": ["test.create(mw::/middle::iface)"],
        "test.create(mw::/middle::run)": ["test.create(mw)"],
        "middle.create(gw)": ["test.create(mw)"],
        "middle.move(iface, gw::/inner::input)": [
            "middle.create(gw)",
            "test.create(mw::/middle::iface::/parent)",
        ],
        "middle.create(gw::/inner::run)": ["middle.create(gw)"],
        "inner.create(input::/parent::/a)": ["middle.move(iface, gw::/inner::input)"],
        "inner.create(input::/parent::/b)": ["middle.move(iface, gw::/inner::input)"],
        "middle.destroy(gw::/inner::input::/parent::/b)": [
            "inner.create(input::/parent::/b)"
        ],
        "middle.destroy(gw::/inner::input::/parent::/a)": [
            "inner.create(input::/parent::/a)"
        ],
        "middle.destroy(gw::/inner::input::/parent)": [
            "middle.destroy(gw::/inner::input::/parent::/b)",
            "middle.destroy(gw::/inner::input::/parent::/a)",
        ],
        "middle.destroy(gw::/inner::input)": [
            "middle.destroy(gw::/inner::input::/parent)"
        ],
        "middle.destroy(gw::/inner::run)": ["middle.create(gw::/inner::run)"],
        "middle.destroy(gw)": [
            "middle.destroy(gw::/inner::input)",
            "middle.destroy(gw::/inner::run)",
        ],
    }


def test_input_carried_through_two_moves_reaches_the_triggered_inner(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/inner::input)": ["test.create(box)"],
        "test.create(outer_holder)": [],
        "test.move(box, outer_holder::/outer::input)": [
            "test.create(box::/inner::input)",
            "test.create(outer_holder)",
        ],
        "test.create(outer_holder::/outer::run)": ["test.create(outer_holder)"],
        "outer.create(middle_holder)": ["test.create(outer_holder)"],
        "outer.move(input, middle_holder::/middle::input)": [
            "outer.create(middle_holder)",
            "test.move(box, outer_holder::/outer::input)",
        ],
        "outer.create(middle_holder::/middle::run)": ["outer.create(middle_holder)"],
        "middle.create(input::/inner::run)": [
            "outer.move(input, middle_holder::/middle::input)"
        ],
        "inner.destroy(input)": ["outer.move(input, middle_holder::/middle::input)"],
    }


def test_occupied_requirement_resolves_to_the_most_recent_fill_before_the_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(gw_a)": [],
        "test.create(gw_b)": [],
        "test.move(source, gw_a::/worker::slot)": [
            "test.create(source)",
            "test.create(gw_a)",
        ],
        "test.move(gw_a::/worker::slot, temp)": [
            "test.move(source, gw_a::/worker::slot)"
        ],
        "test.move(temp, gw_b::/helper::slot)": [
            "test.create(gw_b)",
            "test.move(gw_a::/worker::slot, temp)",
        ],
        "test.create(gw_b::/helper::trigger_pos)": ["test.create(gw_b)"],
        "helper.move(slot, out)": ["test.move(temp, gw_b::/helper::slot)"],
        "test.move(gw_b::/helper::out, gw_a::/worker::slot)": [
            "test.move(gw_a::/worker::slot, temp)",
            "helper.move(slot, out)",
        ],
        "test.create(gw_a::/worker::trigger_pos)": ["test.create(gw_a)"],
        "worker.destroy(slot)": ["test.move(gw_b::/helper::out, gw_a::/worker::slot)"],
    }


def test_caller_consumes_a_nested_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(out)": ["test.create(box::/middle::gw)"],
        "test.move(box::/middle::gw::/inner::out, result)": ["inner.create(out)"],
    }


def test_callee_move_of_a_position_filled_two_levels_up_waits_on_the_caller_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/inner::source)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::gw::/inner::source::/a)": [
            "test.create(box::/middle::gw::/inner::source)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.move(source, holder)": [
            "test.create(box::/middle::gw::/inner::source::/a)",
        ],
    }


def test_callee_empty_waits_on_a_child_a_guaranteeing_action_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/filler::trigger_pos)": [],
        "test.create(/mover::trigger_pos)": [],
        "filler.create(/parent::/child::/gc)": ["test.create(/parent::/child)"],
        "mover.move(/parent::/child, dest)": ["filler.create(/parent::/child::/gc)"],
    }


def test_caller_consumes_a_guarantee_from_two_triggers_down(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(box)": [],
        "test.create(box::/outer::gw)": ["test.create(box)"],
        "test.create(box::/outer::gw::/middle::igw)": ["test.create(box::/outer::gw)"],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.create(gw::/middle::trigger_pos)": ["test.create(box::/outer::gw)"],
        "middle.create(igw::/inner::trigger_pos)": [
            "test.create(box::/outer::gw::/middle::igw)"
        ],
        "inner.create(out)": ["test.create(box::/outer::gw::/middle::igw)"],
        "test.move(box::/outer::gw::/middle::igw::/inner::out, result)": [
            "inner.create(out)"
        ],
    }


def test_triggered_action_input_depends_on_multiple_guarantees(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/parent)": [],
        "test.create(/parent::/child_a)": ["test.create(/parent)"],
        "test.create(/parent::/child_b)": ["test.create(/parent)"],
        "test.create(/filler::trigger_pos)": [],
        "test.create(/mover::trigger_pos)": [],
        "filler.create(/parent::/child_a::/gc)": ["test.create(/parent::/child_a)"],
        "filler.create(/parent::/child_b::/gc)": ["test.create(/parent::/child_b)"],
        "mover.move(/parent, dest)": [
            "filler.create(/parent::/child_a::/gc)",
            "filler.create(/parent::/child_b::/gc)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_CALLER_DEPENDENT_DESTRUCTION_CHILDREN_MISSING)
def test_destruction_cascade_child_state_crosses_two_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.create(source::/b)": ["test.create(source)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/a)",
            "test.create(source::/b)",
        ],
        "middle.move(run, /inner::inner_run)": ["test.move(source, /middle::run)"],
        "inner.destroy_if_occupied(inner_run::/a)": [
            "middle.move(run, /inner::inner_run)"
        ],
        "inner.destroy_if_occupied(inner_run::/b)": [
            "middle.move(run, /inner::inner_run)"
        ],
        "inner.destroy(inner_run)": [
            "inner.destroy_if_occupied(inner_run::/a)",
            "inner.destroy_if_occupied(inner_run::/b)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_CALLER_DEPENDENT_DESTRUCTION_CHILDREN_MISSING)
def test_destruction_cascade_includes_disjoint_child_paths_from_two_callers(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/middle_a::run)": [],
        "test.create(/middle_b::run)": [],
        "middle_a.create(box)": [],
        "middle_a.create(box::/a)": ["middle_a.create(box)"],
        "middle_a.move(box, /destroyer::run)": ["middle_a.create(box::/a)"],
        "middle_a:destroyer.destroy_if_occupied(run::/a)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.destroy_if_occupied(run::/b)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.destroy(run)": [
            "middle_a:destroyer.destroy_if_occupied(run::/a)",
            "middle_a:destroyer.destroy_if_occupied(run::/b)",
        ],
        "middle_b.create(box)": [],
        "middle_b.create(box::/b)": ["middle_b.create(box)"],
        "middle_b.move(box, /destroyer::run)": [
            "middle_b.create(box::/b)",
            "middle_a:destroyer.destroy(run)",
        ],
        "middle_b:destroyer.destroy_if_occupied(run::/a)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.destroy_if_occupied(run::/b)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.destroy(run)": [
            "middle_b:destroyer.destroy_if_occupied(run::/a)",
            "middle_b:destroyer.destroy_if_occupied(run::/b)",
        ],
    }


@pytest.mark.xfail(strict=True, reason=_CALLER_DEPENDENT_DESTRUCTION_CHILDREN_MISSING)
def test_destruction_cascade_includes_shared_child_path_from_two_callers_once(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(/middle_a::run)": [],
        "test.create(/middle_b::run)": [],
        "middle_a.create(box)": [],
        "middle_a.create(box::/child)": ["middle_a.create(box)"],
        "middle_a.move(box, /destroyer::run)": ["middle_a.create(box::/child)"],
        "middle_a:destroyer.destroy_if_occupied(run::/child)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.destroy(run)": [
            "middle_a:destroyer.destroy_if_occupied(run::/child)"
        ],
        "middle_b.create(box)": [],
        "middle_b.create(box::/child)": ["middle_b.create(box)"],
        "middle_b.move(box, /destroyer::run)": [
            "middle_b.create(box::/child)",
            "middle_a:destroyer.destroy(run)",
        ],
        "middle_b:destroyer.destroy_if_occupied(run::/child)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.destroy(run)": [
            "middle_b:destroyer.destroy_if_occupied(run::/child)"
        ],
    }


def test_destruction_cascade_mixes_known_child_states_with_caller_dependent_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(source)": [],
        "test.create(source::/known_empty)": ["test.create(source)"],
        "test.create(source::/maybe_child)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": [
            "test.create(source::/known_empty)",
            "test.create(source::/maybe_child)",
        ],
        "destroyer.move(run, /target)": ["test.move(source, /destroyer::run)"],
        "destroyer.move(/target, local)": ["destroyer.move(run, /target)"],
        "destroyer.move(local::/known_empty, /destination)": [
            "destroyer.move(/target, local)"
        ],
        "destroyer.create(local::/known_occupied)": ["destroyer.move(/target, local)"],
        "destroyer.destroy_if_occupied(local::/maybe_child)": [
            "destroyer.move(/target, local)"
        ],
        "destroyer.destroy(local::/known_occupied)": [
            "destroyer.create(local::/known_occupied)"
        ],
        "destroyer.destroy(local)": [
            "destroyer.move(local::/known_empty, /destination)",
            "destroyer.destroy_if_occupied(local::/maybe_child)",
            "destroyer.destroy(local::/known_occupied)",
        ],
    }
