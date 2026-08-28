from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest

_TEST = "action<my.domain.com:my_lib:/test>"


def test_binding_hole_fans_out_to_multiple_fragments_and_multiple_callee_bindings(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.create(first)": ["test.create(gateway)"],
        "middle.destroy(first)": ["middle.create(first)"],
        "middle.create(second)": ["test.create(gateway)"],
        "middle.destroy(second)": ["middle.create(second)"],
        "middle.create(/child_a::trigger_pos)": ["test.create(gateway)"],
        "child_a.create(scratch)": ["test.create(gateway)"],
        "child_a.destroy(scratch)": ["child_a.create(scratch)"],
        "middle.create(/child_b::trigger_pos)": ["test.create(gateway)"],
        "child_b.create(scratch)": ["test.create(gateway)"],
        "child_b.destroy(scratch)": ["child_b.create(scratch)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_binding_hole_fans_out_to_local_operation_and_multiple_callee_bindings(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_two_child_actions_trigger_in_parallel(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_action_execution_and_empty_rule_use_the_same_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_rule_adds_a_caller_child_operation_to_a_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_consumes_a_child_guarantee_after_an_empty_rule_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_moved_particle_requirement_does_not_affect_replacement_at_origin(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/middle::source)": ["test.create(gateway)"],
        "test.create(gateway::/middle::source::/item)": [
            "test.create(gateway::/middle::source)"
        ],
        "test.create(gateway::/middle::trigger_pos)": ["test.create(gateway)"],
        "middle.move(source, holder)": ["test.create(gateway::/middle::source::/item)"],
        "middle.create(source)": ["middle.move(source, holder)"],
        "middle.create(inner_holder)": ["test.create(gateway)"],
        "middle.move(holder, inner_holder::/inner::input)": [
            "middle.move(source, holder)",
            "middle.create(inner_holder)",
        ],
        "middle.create(inner_holder::/inner::trigger_pos)": [
            "middle.create(inner_holder)"
        ],
        "inner.destroy(input::/item)": [
            "middle.move(holder, inner_holder::/inner::input)"
        ],
        "middle.destroy(inner_holder::/inner::input)": ["inner.destroy(input::/item)"],
        "middle.destroy(inner_holder::/inner::trigger_pos)": [
            "middle.create(inner_holder::/inner::trigger_pos)"
        ],
        "middle.destroy(inner_holder)": [
            "middle.destroy(inner_holder::/inner::input)",
            "middle.destroy(inner_holder::/inner::trigger_pos)",
        ],
        # This dependency belongs on the replacement particle in position<source>,
        # not the caller particle that Middle moved to position<holder>.
        "middle.create(source::/item)": ["middle.create(source)"],
        "middle.destroy(source::/item)": ["middle.create(source::/item)"],
        "middle.destroy(source)": ["middle.destroy(source::/item)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_middle_child_operation_reaches_inner_move_and_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gateway)": ["test.create(box)"],
        "test.create(box::/middle::gateway::/source_particle)": [
            "test.create(box::/middle::gateway)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.move(gateway::/source_particle, gateway::/inner::source)": [
            "test.create(box::/middle::gateway::/source_particle)"
        ],
        "middle.create(gateway::/inner::source::/child)": [
            "middle.move(gateway::/source_particle, gateway::/inner::source)"
        ],
        "middle.create(gateway::/inner::trigger_pos)": [
            "test.create(box::/middle::gateway)"
        ],
        # middle.create(gateway::/inner::source::/child) already waits for the
        # shuttle of the caller-created source particle, so it is the move's
        # only necessary direct dependency.
        "inner.move(source, destination)": [
            "middle.create(gateway::/inner::source::/child)"
        ],
        "inner.destroy(destination::/child)": ["inner.move(source, destination)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_consumes_a_child_guarantee_after_two_action_parent_moves(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
        "middle.move(source, intermediate)": [
            "middle.create(source::/child::trigger_pos)",
            "child.create(result)",
            "test.create(gateway::/middle::source::/marker)",
        ],
        "middle.move(intermediate, holder)": ["middle.move(source, intermediate)"],
        "test.move(gateway::/middle::holder::/child::result, result)": [
            "middle.move(intermediate, holder)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_child_guarantee_with_distinct_occupied_action_parent_and_empty_rule_binding_holes(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_actions_with_identically_named_child_actions_have_distinct_instances(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_two_levels_up_waits_on_the_caller_create(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/value)": ["test.create(box::/middle::gw)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "middle.move(gw::/value, gw::/inner::slot)": [
            "test.create(box::/middle::gw::/value)"
        ],
        # The inner Destroy waits for the particle created two Action Executions
        # earlier to be moved into its interface position.
        "inner.destroy(slot)": ["middle.move(gw::/value, gw::/inner::slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_two_levels_up_waits_on_the_caller_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.move(source, box::/middle::gw::/value)": [
            "test.create(source)",
            "test.create(box::/middle::gw)",
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "middle.move(gw::/value, gw::/inner::slot)": [
            "test.move(source, box::/middle::gw::/value)"
        ],
        # The inner Destroy waits for the particle moved two Action Executions
        # earlier to be moved into its interface position.
        "inner.destroy(slot)": ["middle.move(gw::/value, gw::/inner::slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_rule_propagates_an_intermediate_move_on_a_child_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_move_excludes_reachable_child_move_after_two_substitutions(
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
        "test.create(/middle_action::trigger_pos)": [],
        "middle_action.create(/input::/marker)": ["test.create(/input)"],
        "middle_action.destroy(/input::/marker)": [
            "middle_action.create(/input::/marker)"
        ],
        "middle_action.create(/inner::trigger_pos)": [],
        # The final caller child Move already reaches the Move that emptied origin.
        # The dependency remains unresolved through middle_action, then the second
        # caller substitution excludes the earlier Move from this Move.
        "inner.move(/input, holder)": [
            "middle_action.destroy(/input::/marker)",
            "test.move(/input::/target, holder_c)",
        ],
        "inner.destroy(holder)": ["inner.move(/input, holder)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_empty_rule_preserves_indirect_caller_move_through_intermediate_action(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/input::/a)": ["test.create(/input)"],
        "test.move(/input::/a, /holder)": ["test.create(/input::/a)"],
        "test.move(/holder, /intermediate)": ["test.move(/input::/a, /holder)"],
        "test.create(/input::/b)": ["test.create(/input)"],
        "test.create(/middle_action::trigger_pos)": [],
        "middle_action.create(/inner::trigger_pos)": [],
        "inner.destroy(/intermediate)": ["test.move(/holder, /intermediate)"],
        "inner.move(/input::/b, /intermediate)": [
            "inner.destroy(/intermediate)",
            "test.create(/input::/b)",
        ],
        # The remaining operation on child b reaches the caller's Move on child a
        # through the particle in the separate intermediate position. This is
        # still unresolved while the Empty Rule passes through middle_action.
        "inner.destroy(/input)": ["inner.move(/input::/b, /intermediate)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_that_clears_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/value)": ["test.create(box::/middle::gw)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.move(gw::/value, gw::/inner::slot)": [
            "test.create(box::/middle::gw::/value)"
        ],
        "middle.destroy(gw::/inner::slot)": [
            "middle.move(gw::/value, gw::/inner::slot)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        # The inner action cannot fill slot until the intermediate action has
        # explicitly emptied it.
        "inner.create(slot)": ["middle.destroy(gw::/inner::slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_the_intermediate_callee_destroy_of_an_interface_child(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/holder)": ["test.create(box::/middle::gw)"],
        "test.create(box::/middle::gw::/holder::/a)": [
            "test.create(box::/middle::gw::/holder)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.move(gw::/holder, gw::/inner::holder)": [
            "test.create(box::/middle::gw::/holder::/a)"
        ],
        "middle.destroy(gw::/inner::holder::/a)": [
            "middle.move(gw::/holder, gw::/inner::holder)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        # The inner action cannot fill the child until the intermediate action
        # has explicitly emptied it.
        "inner.create(holder::/a)": ["middle.destroy(gw::/inner::holder::/a)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_by_default_interface_child_waits_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/holder)": ["test.create(box::/middle::gw)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.move(gw::/holder, gw::/inner::holder)": [
            "test.create(box::/middle::gw::/holder)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        # Filling the initially empty child waits until its parent reaches the
        # triggered inner action.
        "inner.create(holder::/a)": ["middle.move(gw::/holder, gw::/inner::holder)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_a_destroy_by_a_caller_that_does_not_trigger_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_empty_requirement_waits_on_an_interface_child_destroy_by_a_caller_that_does_not_trigger_it(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_excludes_parent_dependency_when_source_dependency_is_a_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/box)": [],
        "test.create(/box::/producer::input)": ["test.create(/box)"],
        "producer.move(input, result)": ["test.create(/box::/producer::input)"],
        "test.move(/box::/producer::result, /box::/destination)": [
            "producer.move(input, result)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_move_excludes_non_action_parent_guarantee_fill_dependency(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/input)": [],
        "test.create(/producer::trigger_pos)": [],
        "producer.move(/input, /box)": ["test.create(/input)"],
        "test.create(/consumer::trigger_pos)": [],
        "consumer.create(/box::/item)": ["producer.move(/input, /box)"],
        # The guaranteed Move is already reachable through the more recent child Create,
        # so the Move Rule excludes it after caller substitution.
        "consumer.move(/box::/item, /box::/destination)": [
            "consumer.create(/box::/item)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_fill_dependency_is_removed_through_callee_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/destination)": [],
        "test.move(/destination, temp)": ["test.create(/destination)"],
        "test.move(temp, /slot)": ["test.move(/destination, temp)"],
        "test.create(/mover::trigger_pos)": [],
        "mover.create(/helper::trigger_pos)": [],
        "helper.move(/slot, /out)": ["test.move(temp, /slot)"],
        # The guaranteed Empty Dependency already reaches the caller's Fill
        # Dependency, so the final Move does not depend on it directly.
        "mover.move(/out, /destination)": ["helper.move(/slot, /out)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_pending_move_rule_and_destroy_requirement_binding_holes_share_caller_operation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::target)": ["test.create(gateway)"],
        "test.move(gateway::/worker::target, gateway::/worker::occupied)": [
            "test.create(gateway::/worker::target)"
        ],
        "test.create(gateway::/worker::source)": ["test.create(gateway)"],
        "test.create(gateway::/worker::trigger_pos)": ["test.create(gateway)"],
        "worker.destroy(occupied)": [
            "test.move(gateway::/worker::target, gateway::/worker::occupied)"
        ],
        # The independent source Create does not reach the Fill Dependency, so
        # Worker's Move retains both after its pending relationships are resolved.
        "worker.move(source, target)": [
            "test.move(gateway::/worker::target, gateway::/worker::occupied)",
            "test.create(gateway::/worker::source)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_operation_without_position_dependencies_waits_on_action_parent(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/box)": [],
        "test.create(/box::/worker::trigger_pos)": ["test.create(/box)"],
        "worker.create(result)": ["test.create(/box)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destroy_excludes_callee_operations_superseded_on_child_positions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/worker::input)": ["test.create(box)"],
        "worker.move(input, result)": ["test.create(box::/worker::input)"],
        "test.destroy(box::/worker::result)": ["worker.move(input, result)"],
        "test.destroy(box)": ["test.destroy(box::/worker::result)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_espresso_operation_graph(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_implied_position_children_wait_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/parent)": [],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child1)": ["test.create(/parent)"],
        "inner.create(/parent::/child2)": ["test.create(/parent)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_implied_action_inherits_the_current_actions_parent_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(local)": [],
        "test.create(local::/parent)": ["test.create(local)"],
        "test.create(local::/parent::/middle::trigger_pos)": [
            "test.create(local::/parent)"
        ],
        "middle.create(/inner::trigger_pos)": ["test.create(local::/parent)"],
        "inner.create(scratch)": ["test.create(local::/parent)"],
        "inner.destroy(scratch)": ["inner.create(scratch)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_implied_position_grandchildren_wait_on_the_two_levels_up_caller_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.create(/inner::trigger_pos)": [],
        "inner.create(/parent::/child::/grandchild1)": ["test.create(/parent::/child)"],
        "inner.create(/parent::/child::/grandchild2)": ["test.create(/parent::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_intermediate_callee_operation_suppresses_only_its_caller_path(
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
        "test.create(/parent::/sibling)": ["test.create(/parent)"],
        "test.create(/middle::trigger_pos)": [],
        "middle.destroy(/parent::/child::/grandchild::/greatgrandchild)": [
            "test.create(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "middle.destroy(/parent::/child::/grandchild)": [
            "middle.destroy(/parent::/child::/grandchild::/greatgrandchild)"
        ],
        "middle.create(/inner::trigger_pos)": [],
        "inner.destroy(/parent::/sibling)": [
            "test.create(/parent::/sibling)",
        ],
        "inner.destroy(/parent::/child)": [
            "middle.destroy(/parent::/child::/grandchild)",
        ],
        "inner.destroy(/parent)": [
            "inner.destroy(/parent::/child)",
            "inner.destroy(/parent::/sibling)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_moved_in_parent_children_branch_from_the_carrying_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_input_carried_through_two_moves_reaches_the_triggered_inner(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/child)": ["test.create(box)"],
        "test.create(outer_holder)": [],
        "test.move(box, outer_holder::/outer::input)": [
            "test.create(box::/child)",
            "test.create(outer_holder)",
        ],
        "test.create(outer_holder::/outer::run)": ["test.create(outer_holder)"],
        "outer.create(middle_holder)": ["test.create(outer_holder)"],
        "outer.move(input, middle_holder::/middle::input)": [
            "outer.create(middle_holder)",
            "test.move(box, outer_holder::/outer::input)",
        ],
        "outer.create(middle_holder::/middle::run)": ["outer.create(middle_holder)"],
        "middle.create(inner_holder)": ["outer.create(middle_holder)"],
        "middle.move(input, inner_holder::/inner::input)": [
            "middle.create(inner_holder)",
            "outer.move(input, middle_holder::/middle::input)",
        ],
        "middle.create(inner_holder::/inner::run)": ["middle.create(inner_holder)"],
        # The inner action receives the same particle after two caller moves and
        # the intermediate action's explicit shuttle.
        "inner.destroy(input::/child)": [
            "middle.move(input, inner_holder::/inner::input)"
        ],
        "inner.destroy(input)": ["inner.destroy(input::/child)"],
        "middle.destroy(inner_holder::/inner::run)": [
            "middle.create(inner_holder::/inner::run)"
        ],
        "middle.destroy(inner_holder)": [
            "middle.destroy(inner_holder::/inner::run)",
            "inner.destroy(input)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_requirement_resolves_to_the_most_recent_fill_before_the_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
            "helper.move(slot, out)",
        ],
        "test.create(gw_a::/worker::trigger_pos)": ["test.create(gw_a)"],
        "worker.destroy(slot)": ["test.move(gw_b::/helper::out, gw_a::/worker::slot)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_consumes_a_nested_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        "inner.create(out)": ["test.create(box::/middle::gw)"],
        "test.move(box::/middle::gw::/inner::out, result)": ["inner.create(out)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_move_of_a_position_filled_two_levels_up_waits_on_the_caller_child_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/middle::gw)": ["test.create(box)"],
        "test.create(box::/middle::gw::/source_particle)": [
            "test.create(box::/middle::gw)"
        ],
        "test.create(box::/middle::gw::/source_particle::/a)": [
            "test.create(box::/middle::gw::/source_particle)"
        ],
        "test.create(box::/middle::trigger_pos)": ["test.create(box)"],
        "middle.move(gw::/source_particle, gw::/inner::source)": [
            "test.create(box::/middle::gw::/source_particle::/a)"
        ],
        "middle.create(gw::/inner::trigger_pos)": ["test.create(box::/middle::gw)"],
        # The inner action's move waits on the child filled two actions earlier.
        "inner.move(source, holder)": [
            "middle.move(gw::/source_particle, gw::/inner::source)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_empty_waits_on_a_child_a_guaranteeing_action_filled(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/parent)": [],
        "test.create(/parent::/child)": ["test.create(/parent)"],
        "test.create(/filler::trigger_pos)": [],
        "test.create(/mover::trigger_pos)": [],
        "filler.create(/parent::/child::/gc)": ["test.create(/parent::/child)"],
        "mover.move(/parent::/child, dest)": ["filler.create(/parent::/child::/gc)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_consumes_a_guarantee_from_two_triggers_down(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(box)": [],
        "test.create(box::/outer::gw)": ["test.create(box)"],
        "test.create(box::/outer::trigger_pos)": ["test.create(box)"],
        "outer.create(gw::/middle::igw)": ["test.create(box::/outer::gw)"],
        "outer.create(gw::/middle::trigger_pos)": ["test.create(box::/outer::gw)"],
        "middle.create(igw::/inner::trigger_pos)": ["outer.create(gw::/middle::igw)"],
        "inner.create(out)": ["outer.create(gw::/middle::igw)"],
        "middle.move(igw::/inner::out, igw::/out_value)": ["inner.create(out)"],
        "outer.move(gw::/middle::igw::/out_value, gw::/out_value)": [
            "middle.move(igw::/inner::out, igw::/out_value)"
        ],
        # The caller consumes the guarantee after each intermediate action has
        # explicitly shuttled the particle through its own contracted position.
        "test.move(box::/outer::gw::/out_value, result)": [
            "outer.move(gw::/middle::igw::/out_value, gw::/out_value)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_transitive_child_guarantee_follows_particle_through_move(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/outer::source)": ["test.create(gateway)"],
        "test.create(gateway::/outer::trigger_pos)": ["test.create(gateway)"],
        "outer.create(middle_holder)": ["test.create(gateway)"],
        "outer.move(source, middle_holder::/middle::inner_parent)": [
            "outer.create(middle_holder)",
            "test.create(gateway::/outer::source)",
        ],
        "outer.create(middle_holder::/middle::trigger_pos)": [
            "outer.create(middle_holder)"
        ],
        "middle.create(inner_holder)": ["outer.create(middle_holder)"],
        "middle.move(inner_parent, inner_holder::/inner::input)": [
            "middle.create(inner_holder)",
            "outer.move(source, middle_holder::/middle::inner_parent)",
        ],
        "middle.create(inner_holder::/inner::trigger_pos)": [
            "middle.create(inner_holder)"
        ],
        "inner.create(input::/result_value)": [
            "middle.move(inner_parent, inner_holder::/inner::input)"
        ],
        "middle.move(inner_holder::/inner::input::/result_value, result_holder)": [
            "inner.create(input::/result_value)"
        ],
        "middle.move(inner_holder::/inner::input, inner_parent)": [
            "middle.move(inner_holder::/inner::input::/result_value, result_holder)"
        ],
        "middle.move(result_holder, inner_parent::/result_value)": [
            "middle.move(inner_holder::/inner::input, inner_parent)"
        ],
        "middle.destroy(inner_holder::/inner::trigger_pos)": [
            "middle.create(inner_holder::/inner::trigger_pos)"
        ],
        "middle.destroy(inner_holder)": [
            "middle.move(inner_holder::/inner::input, inner_parent)",
            "middle.destroy(inner_holder::/inner::trigger_pos)",
        ],
        "outer.move(middle_holder::/middle::inner_parent::/result_value, result_holder)": [
            "middle.move(result_holder, inner_parent::/result_value)"
        ],
        "outer.move(middle_holder::/middle::inner_parent, destination)": [
            "outer.move(middle_holder::/middle::inner_parent::/result_value, result_holder)"
        ],
        "outer.move(result_holder, destination::/result_value)": [
            "outer.move(middle_holder::/middle::inner_parent, destination)"
        ],
        "outer.destroy(middle_holder::/middle::trigger_pos)": [
            "outer.create(middle_holder::/middle::trigger_pos)"
        ],
        "outer.destroy(middle_holder)": [
            "outer.move(middle_holder::/middle::inner_parent, destination)",
            "outer.destroy(middle_holder::/middle::trigger_pos)",
        ],
        # The final consumer waits for the guaranteed child to follow its parent
        # through both actions' explicit shuttles and moves.
        "test.move(gateway::/outer::destination::/result_value, result)": [
            "outer.move(result_holder, destination::/result_value)"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_later_transitive_guarantee_wins_between_sibling_calls(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/run_both::trigger_pos)": [],
        "test.create(/item)": ["empty_item.destroy(/item)"],
        "run_both.create(/call_fill::trigger_pos)": [],
        "run_both.create(/call_empty::trigger_pos)": [],
        "call_fill.create(/fill_item::trigger_pos)": [],
        "fill_item.create(/item)": [],
        "call_empty.create(/empty_item::trigger_pos)": [],
        "empty_item.destroy(/item)": ["fill_item.create(/item)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_occupied_guarantee_flows_from_direct_callee_to_transitive_callee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/fill_item::trigger_pos)": [],
        "test.create(/outer::trigger_pos)": [],
        "fill_item.create(/item)": [],
        "outer.create(/middle::trigger_pos)": [],
        "middle.create(/empty_item::trigger_pos)": [],
        # The direct callee's occupied Guarantee crosses two later Action
        # Executions before satisfying the Empty Rule for this Destroy.
        "empty_item.destroy(/item)": ["fill_item.create(/item)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_deep_diamond_operations_on_the_same_implied_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/left::trigger_pos)": [],
        "test.create(/right::trigger_pos)": [],
        "left.create(/left_child::trigger_pos)": [],
        "left_child.create(/marker)": [],
        "right.create(/right_child::trigger_pos)": [],
        "right_child.destroy(/marker)": ["left_child.create(/marker)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_callee_move_empty_rule_binding_hole_binds_multiple_caller_guarantees(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
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
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destruction_cascade_child_state_crosses_two_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.create(source::/b)": ["test.create(source)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/a)",
            "test.create(source::/b)",
        ],
        "middle.move(run, /inner::inner_run)": ["test.move(source, /middle::run)"],
        "inner.destroy(inner_run::/a)": ["middle.move(run, /inner::inner_run)"],
        "inner.destroy(inner_run::/b)": ["middle.move(run, /inner::inner_run)"],
        "inner.destroy(inner_run)": [
            "inner.destroy(inner_run::/b)",
            "inner.destroy(inner_run::/a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_auto_destruction_child_state_crosses_two_actions(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/a)": ["test.create(source)"],
        "test.create(source::/b)": ["test.create(source)"],
        "test.move(source, /middle::run)": [
            "test.create(source::/a)",
            "test.create(source::/b)",
        ],
        "middle.move(run, /inner::inner_run)": ["test.move(source, /middle::run)"],
        "inner.move(inner_run, local)": ["middle.move(run, /inner::inner_run)"],
        # The Destruction Contract crosses middle, and both caller-only child
        # Destroys must finish before inner automatically destroys local.
        "inner.destroy(local::/a)": ["inner.move(inner_run, local)"],
        "inner.destroy(local::/b)": ["inner.move(inner_run, local)"],
        "inner.destroy(local)": [
            "inner.destroy(local::/b)",
            "inner.destroy(local::/a)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destruction_cascade_includes_disjoint_child_paths_from_two_callers(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/middle_a::run)": [],
        "test.create(/middle_b::run)": [],
        "middle_a.create(box)": [],
        "middle_a.create(box::/a)": ["middle_a.create(box)"],
        "middle_a.move(box, /destroyer::run)": ["middle_a.create(box::/a)"],
        "middle_a:destroyer.destroy(run::/a)": ["middle_a.move(box, /destroyer::run)"],
        "middle_a:destroyer.destroy(run)": [
            "middle_a:destroyer.destroy(run::/a)",
        ],
        "middle_b.create(box)": [],
        "middle_b.create(box::/b)": ["middle_b.create(box)"],
        "middle_b.move(box, /destroyer::run)": [
            "middle_b.create(box::/b)",
            "middle_a:destroyer.destroy(run)",
        ],
        "middle_b:destroyer.destroy(run::/b)": ["middle_b.move(box, /destroyer::run)"],
        "middle_b:destroyer.destroy(run)": [
            "middle_b:destroyer.destroy(run::/b)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destruction_cascade_includes_shared_child_path_from_two_callers_once(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/middle_a::run)": [],
        "test.create(/middle_b::run)": [],
        "middle_a.create(box)": [],
        "middle_a.create(box::/child)": ["middle_a.create(box)"],
        "middle_a.move(box, /destroyer::run)": ["middle_a.create(box::/child)"],
        "middle_a:destroyer.destroy(run::/child)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.destroy(run)": ["middle_a:destroyer.destroy(run::/child)"],
        "middle_b.create(box)": [],
        "middle_b.create(box::/child)": ["middle_b.create(box)"],
        "middle_b.move(box, /destroyer::run)": [
            "middle_b.create(box::/child)",
            "middle_a:destroyer.destroy(run)",
        ],
        "middle_b:destroyer.destroy(run::/child)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.destroy(run)": ["middle_b:destroyer.destroy(run::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_caller_contribution_and_callee_guarantee_precede_parent_destroy(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/sibling)": ["test.create(source)"],
        "test.move(source, /destroyer::parent)": ["test.create(source::/sibling)"],
        "test.create(/destroyer::trigger_pos)": [],
        "destroyer.create(parent::/maker::trigger_pos)": [
            "test.move(source, /destroyer::parent)"
        ],
        "maker.create(result)": ["test.move(source, /destroyer::parent)"],
        "maker.destroy(result)": ["maker.create(result)"],
        "destroyer.destroy(parent::/sibling)": [
            "test.move(source, /destroyer::parent)"
        ],
        "destroyer.destroy(parent::/maker::trigger_pos)": [
            "destroyer.create(parent::/maker::trigger_pos)"
        ],
        # Both the caller-contributed sibling Destroy and the callee-guaranteed
        # particle's Destroy must finish before the parent Destroy.
        "destroyer.destroy(parent)": [
            "destroyer.destroy(parent::/sibling)",
            "maker.destroy(result)",
            "destroyer.destroy(parent::/maker::trigger_pos)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destruction_cascade_mixes_known_child_states_with_caller_dependent_state(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/known_empty)": ["test.create(source)"],
        "test.create(source::/known_occupied)": ["test.create(source)"],
        "test.destroy(source::/known_occupied)": [
            "test.create(source::/known_occupied)"
        ],
        "test.create(source::/maybe_child)": ["test.create(source)"],
        "test.move(source, /destroyer::run)": [
            "test.create(source::/known_empty)",
            "test.destroy(source::/known_occupied)",
            "test.create(source::/maybe_child)",
        ],
        "destroyer.move(run, /target)": ["test.move(source, /destroyer::run)"],
        "destroyer.move(/target, local)": ["destroyer.move(run, /target)"],
        "destroyer.move(local::/known_empty, /destination)": [
            "destroyer.move(/target, local)"
        ],
        "destroyer.create(local::/known_occupied)": ["destroyer.move(/target, local)"],
        # The destruction cascade includes /maybe_child because the caller knows
        # it is occupied, even though /destroyer does not constrain it on local.
        "destroyer.destroy(local::/maybe_child)": ["destroyer.move(/target, local)"],
        "destroyer.destroy(local::/known_occupied)": [
            "destroyer.create(local::/known_occupied)"
        ],
        # The parent Destroy waits for the final operations representing both
        # callee-known child states and the caller-dependent child.
        "destroyer.destroy(local)": [
            "destroyer.destroy(local::/maybe_child)",
            "destroyer.move(local::/known_empty, /destination)",
            "destroyer.destroy(local::/known_occupied)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_same_callee_callers_assign_child_qualities_in_opposite_orders(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(/middle_a::run)": [],
        "test.create(/middle_b::run)": [],
        "middle_a.create(box)": [],
        "middle_a.create(box::/child)": ["middle_a.create(box)"],
        "middle_a.create(box::/sibling)": ["middle_a.create(box)"],
        "middle_a.move(box, /destroyer::run)": [
            "middle_a.create(box::/child)",
            "middle_a.create(box::/sibling)",
        ],
        # Assigning /child before /sibling does not order the sibling Destroy and
        # the first Move of the child particle relative to each other.
        "middle_a:destroyer.destroy(run::/sibling)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.move(run::/child, keeper)": [
            "middle_a.move(box, /destroyer::run)"
        ],
        "middle_a:destroyer.move(keeper, run::/child)": [
            "middle_a:destroyer.move(run::/child, keeper)"
        ],
        "middle_a:destroyer.destroy(run::/child)": [
            "middle_a:destroyer.move(keeper, run::/child)"
        ],
        # The parent Destroy waits for both independently ordered child Destroys.
        "middle_a:destroyer.destroy(run)": [
            "middle_a:destroyer.destroy(run::/sibling)",
            "middle_a:destroyer.destroy(run::/child)",
        ],
        "middle_b.create(box)": [],
        "middle_b.create(box::/sibling)": ["middle_b.create(box)"],
        "middle_b.create(box::/child)": ["middle_b.create(box)"],
        "middle_b.move(box, /destroyer::run)": [
            "middle_b.create(box::/sibling)",
            "middle_b.create(box::/child)",
            "middle_a:destroyer.destroy(run)",
        ],
        # Assigning /sibling before /child produces the same independent
        # dependencies for the sibling Destroy and the first child Move.
        "middle_b:destroyer.destroy(run::/sibling)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.move(run::/child, keeper)": [
            "middle_b.move(box, /destroyer::run)"
        ],
        "middle_b:destroyer.move(keeper, run::/child)": [
            "middle_b:destroyer.move(run::/child, keeper)"
        ],
        "middle_b:destroyer.destroy(run::/child)": [
            "middle_b:destroyer.move(keeper, run::/child)"
        ],
        # The parent Destroy again waits for both child Destroys.
        "middle_b:destroyer.destroy(run)": [
            "middle_b:destroyer.destroy(run::/sibling)",
            "middle_b:destroyer.destroy(run::/child)",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
