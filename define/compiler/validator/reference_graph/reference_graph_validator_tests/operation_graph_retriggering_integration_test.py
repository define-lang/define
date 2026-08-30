from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator.reference_graph.operation_graph_renderer import (
    assert_operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest

_TEST = "action<my.domain.com:my_lib:/test>"


def test_action_that_destroys_its_own_trigger_position_is_triggered_twice(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_destroying_action_reused_with_known_child_empty_then_occupied(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(first::/child)": ["test.create(first)"],
        "test.destroy(first::/child)": ["test.create(first::/child)"],
        "test.move(first, /destroyer::run)": ["test.destroy(first::/child)"],
        "destroyer.move(run, /target)": ["test.move(first, /destroyer::run)"],
        "destroyer.destroy(/target)": ["destroyer.move(run, /target)"],
        "test.create(second)": [],
        "test.create(second::/child)": ["test.create(second)"],
        "test.move(second, /destroyer::run)": [
            "test.create(second::/child)",
            "destroyer.move(run, /target)",
        ],
        "destroyer#2.move(run, /target)": [
            "test.move(second, /destroyer::run)",
            "destroyer.destroy(/target)",
        ],
        "destroyer#2.destroy(/target::/child)": ["destroyer#2.move(run, /target)"],
        "destroyer#2.destroy(/target)": ["destroyer#2.destroy(/target::/child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_reused_callee_receives_distinct_destruction_connections_per_execution(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(first::/first_child)": ["test.create(first)"],
        "test.move(first, /destroyer::run)": ["test.create(first::/first_child)"],
        "destroyer.move(run, /target)": ["test.move(first, /destroyer::run)"],
        # The first caller-known child Destroy belongs to the first Action Execution.
        "destroyer.destroy(/target::/first_child)": ["destroyer.move(run, /target)"],
        "destroyer.destroy(/target)": ["destroyer.destroy(/target::/first_child)"],
        "test.create(second)": [],
        "test.create(second::/second_child)": ["test.create(second)"],
        "test.move(second, /destroyer::run)": [
            "test.create(second::/second_child)",
            "destroyer.move(run, /target)",
        ],
        "destroyer#2.move(run, /target)": [
            "test.move(second, /destroyer::run)",
            "destroyer.destroy(/target)",
        ],
        # The second caller-known child Destroy belongs to the second Action
        # Trigger rather than the first one.
        "destroyer#2.destroy(/target::/second_child)": [
            "destroyer#2.move(run, /target)"
        ],
        "destroyer#2.destroy(/target)": ["destroyer#2.destroy(/target::/second_child)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_repeated_destroying_action_invocations_include_caller_dependent_children(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(first)": [],
        "test.create(first::/child)": ["test.create(first)"],
        "test.move(first, /destroyer::run)": ["test.create(first::/child)"],
        "destroyer.destroy(run::/child)": ["test.move(first, /destroyer::run)"],
        "destroyer.destroy(run)": [
            "destroyer.destroy(run::/child)",
        ],
        "test.create(second)": [],
        "test.create(second::/child)": ["test.create(second)"],
        "test.move(second, /destroyer::run)": [
            "test.create(second::/child)",
            "destroyer.destroy(run)",
        ],
        "destroyer#2.destroy(run::/child)#2": ["test.move(second, /destroyer::run)"],
        "destroyer#2.destroy(run)": [
            "destroyer#2.destroy(run::/child)#2",
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_only_relevant_retrigger_receives_forwarded_destruction_connections(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(source)": [],
        "test.create(source::/child)": ["test.create(source)"],
        "test.move(source, /middle::run)": ["test.create(source::/child)"],
        # Only the first Action Execution receives the caller-known child Destroy.
        "destroyer.destroy(run::/child)": ["middle.move(run, /destroyer::run)"],
        "middle.move(run, /destroyer::run)": ["test.move(source, /middle::run)"],
        "middle.create(local)": [],
        "middle.move(local, /destroyer::run)": [
            "middle.create(local)",
            "destroyer.destroy(run)",
        ],
        "destroyer.destroy(run)": ["destroyer.destroy(run::/child)"],
        # The locally created particle has no caller-known child, so its Destroy
        # depends directly on the second Action Execution's Move.
        "destroyer#2.destroy(run)": ["middle.move(local, /destroyer::run)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_retriggered_action_resolves_requirements_within_each_invocation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/maker::trigger_pos)": ["test.create(gw)"],
        "maker.create(out)": ["test.create(gw)"],
        "test.move(gw::/maker::out, first_result)": ["maker.create(out)"],
        "test.destroy(gw::/maker::trigger_pos)": [
            "test.create(gw::/maker::trigger_pos)"
        ],
        "test.create(gw::/maker::trigger_pos)#2": [
            "test.destroy(gw::/maker::trigger_pos)"
        ],
        # The Create from the second time /maker is triggered waits for the
        # caller to move the particle from the first time out of the interface
        # position.
        "maker#2.create(out)": ["test.move(gw::/maker::out, first_result)"],
        "test.move(gw::/maker::out, second_result)": ["maker#2.create(out)"],
        "test.destroy(gw::/maker::trigger_pos)#2": [
            "test.create(gw::/maker::trigger_pos)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_retriggered_action_resolves_both_triggers_to_the_one_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/maker::held)": ["test.create(gw)"],
        "test.create(gw::/maker::trigger_pos)": ["test.create(gw)"],
        # The caller's one parent Create satisfies /maker's occupied requirement
        # both times it is triggered.
        "maker.create(held::/c)": ["test.create(gw::/maker::held)"],
        "test.destroy(gw::/maker::held::/c)": ["maker.create(held::/c)"],
        "test.destroy(gw::/maker::trigger_pos)": [
            "test.create(gw::/maker::trigger_pos)"
        ],
        "test.create(gw::/maker::trigger_pos)#2": [
            "test.destroy(gw::/maker::trigger_pos)"
        ],
        # The caller's Destroy of the first particle precedes the second Create
        # at the same child position.
        "maker#2.create(held::/c)": ["test.destroy(gw::/maker::held::/c)"],
        "test.destroy(gw::/maker::held::/c)#2": ["maker#2.create(held::/c)"],
        "test.destroy(gw::/maker::held)": ["test.destroy(gw::/maker::held::/c)#2"],
        "test.destroy(gw::/maker::trigger_pos)#2": [
            "test.create(gw::/maker::trigger_pos)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_retriggered_action_uses_prior_unchanged_interface_guarantee(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gateway)": [],
        "test.create(gateway::/worker::item)": ["test.create(gateway)"],
        "test.create(gateway::/worker::trigger_pos)": ["test.create(gateway)"],
        "worker.move(item, holder)": ["test.create(gateway::/worker::item)"],
        "worker.move(holder, item)": ["worker.move(item, holder)"],
        "worker.destroy(trigger_pos)": ["test.create(gateway::/worker::trigger_pos)"],
        "test.create(gateway::/worker::trigger_pos)#2": ["worker.destroy(trigger_pos)"],
        # The second Action Execution uses the first execution's Unchanged
        # Guarantee for item, independently of the recreated trigger_pos.
        "worker#2.move(item, holder)": ["worker.move(holder, item)"],
        "worker#2.move(holder, item)": ["worker#2.move(item, holder)"],
        "worker#2.destroy(trigger_pos)": [
            "test.create(gateway::/worker::trigger_pos)#2"
        ],
        "test.destroy(gateway::/worker::item)": ["worker#2.move(holder, item)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_retriggered_action_with_no_guarantees_runs_once_per_execution(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(gw)": [],
        "test.create(gw::/worker::trigger_pos)": ["test.create(gw)"],
        "test.destroy(gw::/worker::trigger_pos)": [
            "test.create(gw::/worker::trigger_pos)"
        ],
        "test.create(gw::/worker::trigger_pos)#2": [
            "test.destroy(gw::/worker::trigger_pos)"
        ],
        "worker.create(scratch)": ["test.create(gw)"],
        "worker.destroy(scratch)": ["worker.create(scratch)"],
        # The second trigger produces the worker's operations a second time even
        # though the action has no guarantees.
        "worker#2.create(scratch)": ["test.create(gw)"],
        "worker#2.destroy(scratch)": ["worker#2.create(scratch)"],
        "test.destroy(gw::/worker::trigger_pos)#2": [
            "test.create(gw::/worker::trigger_pos)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_two_actions_each_triggering_one_action_twice_number_its_invocations_across_the_program(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(holder_first)": [],
        "test.create(holder_first::/first::trigger_pos)": ["test.create(holder_first)"],
        "test.create(holder_second)": [],
        "test.create(holder_second::/second::trigger_pos)": [
            "test.create(holder_second)"
        ],
        "test.destroy(holder_first::/first::trigger_pos)": [
            "test.create(holder_first::/first::trigger_pos)"
        ],
        "test.destroy(holder_second::/second::trigger_pos)": [
            "test.create(holder_second::/second::trigger_pos)"
        ],
        "first.create(gw)": ["test.create(holder_first)"],
        "first.create(gw::/worker::trigger_pos)": ["first.create(gw)"],
        "first.destroy(gw::/worker::trigger_pos)": [
            "first.create(gw::/worker::trigger_pos)"
        ],
        "first.create(gw::/worker::trigger_pos)#2": [
            "first.destroy(gw::/worker::trigger_pos)"
        ],
        "first.destroy(gw::/worker::trigger_pos)#2": [
            "first.create(gw::/worker::trigger_pos)#2"
        ],
        "first.destroy(gw)": ["first.destroy(gw::/worker::trigger_pos)#2"],
        "second.create(gw)": ["test.create(holder_second)"],
        "second.create(gw::/worker::trigger_pos)": ["second.create(gw)"],
        "second.destroy(gw::/worker::trigger_pos)": [
            "second.create(gw::/worker::trigger_pos)"
        ],
        "second.create(gw::/worker::trigger_pos)#2": [
            "second.destroy(gw::/worker::trigger_pos)"
        ],
        "second.destroy(gw::/worker::trigger_pos)#2": [
            "second.create(gw::/worker::trigger_pos)#2"
        ],
        "second.destroy(gw)": ["second.destroy(gw::/worker::trigger_pos)#2"],
        "first:worker.create(scratch)": ["first.create(gw)"],
        "first:worker.destroy(scratch)": ["first:worker.create(scratch)"],
        # The worker action runs twice when /first is triggered; these are its
        # second run's operations.
        "first:worker#2.create(scratch)": ["first.create(gw)"],
        "first:worker#2.destroy(scratch)": ["first:worker#2.create(scratch)"],
        "second:worker.create(scratch)": ["second.create(gw)"],
        "second:worker.destroy(scratch)": ["second:worker.create(scratch)"],
        # The worker action also runs twice when /second is triggered; these are
        # its second run's operations.
        "second:worker#2.create(scratch)": ["second.create(gw)"],
        "second:worker#2.destroy(scratch)": ["second:worker#2.create(scratch)"],
    }
    assert_operation_dependencies(result.operation_graphs, expected)


def test_retriggered_action_that_retriggers_an_action_names_its_callee_per_invocation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    expected = {
        "test.create(holder)": [],
        "test.create(holder::/middle::trigger_pos)": ["test.create(holder)"],
        "test.destroy(holder::/middle::trigger_pos)": [
            "test.create(holder::/middle::trigger_pos)"
        ],
        "test.create(holder::/middle::trigger_pos)#2": [
            "test.destroy(holder::/middle::trigger_pos)"
        ],
        "middle.create(gw)": ["test.create(holder)"],
        "middle.create(gw::/worker::trigger_pos)": ["middle.create(gw)"],
        "middle.destroy(gw::/worker::trigger_pos)": [
            "middle.create(gw::/worker::trigger_pos)"
        ],
        "middle.create(gw::/worker::trigger_pos)#2": [
            "middle.destroy(gw::/worker::trigger_pos)"
        ],
        "middle.destroy(gw::/worker::trigger_pos)#2": [
            "middle.create(gw::/worker::trigger_pos)#2"
        ],
        "middle.destroy(gw)": ["middle.destroy(gw::/worker::trigger_pos)#2"],
        "middle:worker.create(scratch)": ["middle.create(gw)"],
        "middle:worker.destroy(scratch)": ["middle:worker.create(scratch)"],
        "middle:worker#2.create(scratch)": ["middle.create(gw)"],
        "middle:worker#2.destroy(scratch)": ["middle:worker#2.create(scratch)"],
        "middle#2.create(gw)": ["test.create(holder)"],
        "middle#2.create(gw::/worker::trigger_pos)": ["middle#2.create(gw)"],
        "middle#2.destroy(gw::/worker::trigger_pos)": [
            "middle#2.create(gw::/worker::trigger_pos)"
        ],
        "middle#2.create(gw::/worker::trigger_pos)#2": [
            "middle#2.destroy(gw::/worker::trigger_pos)"
        ],
        "middle#2.destroy(gw::/worker::trigger_pos)#2": [
            "middle#2.create(gw::/worker::trigger_pos)#2"
        ],
        "middle#2.destroy(gw)": ["middle#2.destroy(gw::/worker::trigger_pos)#2"],
        "middle#2:worker.create(scratch)": ["middle#2.create(gw)"],
        "middle#2:worker.destroy(scratch)": ["middle#2:worker.create(scratch)"],
        # When /middle runs for the second time, it triggers /worker twice; these
        # are the fourth worker run's operations.
        "middle#2:worker#2.create(scratch)": ["middle#2.create(gw)"],
        "middle#2:worker#2.destroy(scratch)": ["middle#2:worker#2.create(scratch)"],
        "test.destroy(holder::/middle::trigger_pos)#2": [
            "test.create(holder::/middle::trigger_pos)#2"
        ],
    }
    assert_operation_dependencies(result.operation_graphs, expected)
