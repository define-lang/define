from define.compiler import conftest
from define.compiler.validator.reference_graph.operation_graph_renderer import (
    operation_dependencies,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"


def test_action_that_destroys_its_own_trigger_position_is_triggered_twice(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gateway)": [],
        "test.create(gateway::/other::trigger_pos)": ["test.create(gateway)"],
        "other.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)"],
        "test.create(gateway::/other::trigger_pos)#2": ["other.destroy(trigger_pos)"],
        "other#2.destroy(trigger_pos)": ["test.create(gateway::/other::trigger_pos)#2"],
    }


def test_retriggered_action_resolves_requirements_within_each_invocation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "maker#2.create(out)": ["test.move(gw::/maker::out, first_result)"],
        "test.move(gw::/maker::out, second_result)": ["maker#2.create(out)"],
    }


def test_retriggered_action_resolves_both_triggers_to_the_one_parent_fill(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(gw)": [],
        "test.create(gw::/maker::held)": ["test.create(gw)"],
        "test.create(gw::/maker::trigger_pos)": ["test.create(gw)"],
        "maker.create(held::/c)": ["test.create(gw::/maker::held)"],
        "test.destroy(gw::/maker::held::/c)": ["maker.create(held::/c)"],
        "test.destroy(gw::/maker::trigger_pos)": [
            "test.create(gw::/maker::trigger_pos)"
        ],
        "test.create(gw::/maker::trigger_pos)#2": [
            "test.destroy(gw::/maker::trigger_pos)"
        ],
        "maker#2.create(held::/c)": ["test.destroy(gw::/maker::held::/c)"],
    }


def test_retriggered_action_with_no_guarantees_runs_once_per_trigger(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "worker#2.create(scratch)": ["test.create(gw)"],
        "worker#2.destroy(scratch)": ["worker#2.create(scratch)"],
    }


def test_two_actions_each_triggering_one_action_twice_number_its_invocations_across_the_program(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
        "test.create(holder_first)": [],
        "test.create(holder_first::/first::trigger_pos)": ["test.create(holder_first)"],
        "test.create(holder_second)": [],
        "test.create(holder_second::/second::trigger_pos)": [
            "test.create(holder_second)"
        ],
        "first.create(gw)": ["test.create(holder_first)"],
        "first.create(gw::/worker::trigger_pos)": ["first.create(gw)"],
        "first.destroy(gw::/worker::trigger_pos)": [
            "first.create(gw::/worker::trigger_pos)"
        ],
        "first.create(gw::/worker::trigger_pos)#2": [
            "first.destroy(gw::/worker::trigger_pos)"
        ],
        "first.destroy(gw)": ["first.create(gw::/worker::trigger_pos)#2"],
        "second.create(gw)": ["test.create(holder_second)"],
        "second.create(gw::/worker::trigger_pos)": ["second.create(gw)"],
        "second.destroy(gw::/worker::trigger_pos)": [
            "second.create(gw::/worker::trigger_pos)"
        ],
        "second.create(gw::/worker::trigger_pos)#2": [
            "second.destroy(gw::/worker::trigger_pos)"
        ],
        "second.destroy(gw)": ["second.create(gw::/worker::trigger_pos)#2"],
        "first:worker.create(scratch)": ["first.create(gw)"],
        "first:worker.destroy(scratch)": ["first:worker.create(scratch)"],
        "first:worker#2.create(scratch)": ["first.create(gw)"],
        "first:worker#2.destroy(scratch)": ["first:worker#2.create(scratch)"],
        "second:worker.create(scratch)": ["second.create(gw)"],
        "second:worker.destroy(scratch)": ["second:worker.create(scratch)"],
        "second:worker#2.create(scratch)": ["second.create(gw)"],
        "second:worker#2.destroy(scratch)": ["second:worker#2.create(scratch)"],
    }


def test_retriggered_action_that_retriggers_an_action_names_its_callee_per_invocation(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
    assert operation_dependencies(result.operation_graphs) == {
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
        "middle.destroy(gw)": ["middle.create(gw::/worker::trigger_pos)#2"],
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
        "middle#2.destroy(gw)": ["middle#2.create(gw::/worker::trigger_pos)#2"],
        "middle#2:worker.create(scratch)": ["middle#2.create(gw)"],
        "middle#2:worker.destroy(scratch)": ["middle#2:worker.create(scratch)"],
        "middle#2:worker#2.create(scratch)": ["middle#2.create(gw)"],
        "middle#2:worker#2.destroy(scratch)": ["middle#2:worker#2.create(scratch)"],
    }
