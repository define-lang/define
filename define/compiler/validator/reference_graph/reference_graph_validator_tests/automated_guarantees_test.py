# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_CONSTRUCT = "action<my.domain.com:my_lib:/construct>"


def test_create_in_interface_position_starts_empty(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Creating in an interface position that starts empty succeeds."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        destroy the particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_create_twice_in_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Creating twice in the same interface position produces CreateInOccupiedPositionDiagnostic."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        destroy the particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 12
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")


def test_untouched_interface_position_preserved_after_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An interface position's state is preserved through a trigger if the action doesn't touch it."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 12
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.UnreferencedPositionDiagnostic)
    assert all_diags[1].position_name == "position<item>"
    assert all_diags[1].location.line == 3
    assert all_diags[1].location.column == 25
    assert all_diags[1].location.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_move_from_guarantee_emptied_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving from an interface position that the action's guarantee emptied produces MoveFromEmptyInterfacePositionDiagnostic."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<trigger_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<trigger_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.MoveFromEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_guaranteed_empty_position_allows_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position guaranteed empty by the action allows a create."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_guaranteed_occupied_position_rejects_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position guaranteed occupied by the action (via create) rejects a second create."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_trigger_position_stays_occupied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The trigger position remains occupied after the trigger fires; creating in it again fails."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].populated_at.line == 12
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_cycle_after_guarantee_empties_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the action moves the trigger particle away, the trigger position is empty after trigger, allowing re-trigger."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_fails_when_guarantee_filled_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Second trigger fails when the action's guarantee filled a position the action requires empty."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos> to position<_sink>.\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<item>",
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 9,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_fails_when_existing_guarantee_leaves_position_occupied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Second trigger fails when the dest position is still occupied from the first trigger's move guarantee."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos> to position<_sink>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is True
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dest>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 19,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_fails_occupied_requirement_after_guarantee_empties(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Second trigger fails both occupied and empty requirements due to the first trigger's move guarantees."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos> to position<_sink>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[1].required_empty is True
    assert all_diags[1].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[1].location.line == 16
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dest>",
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 16,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 10,
            "column": 48,
            "file_path": "other.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_succeeds_with_proper_state_management(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Second trigger succeeds when the caller properly restores state between trigger cycles."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<trigger_pos> to position<_sink>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<dest> to position<sink>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_particle_identity_preserved_through_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a particle moved by the action's guarantee retains its constraint qualities."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</quality_a>.\n"
                "            it has the position</quality_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</quality_a>.\n"
                "        create a particle in position<item>::position</quality_b>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<wide> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_a>.\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<wide>.\n"
                "        move the particle in position<wide> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<dest> to position<wide>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_guaranteed_empty_position_allows_move_to(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position guaranteed empty by the action allows move-to."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_occupied_by_new_allows_move_from(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position guaranteed occupied via the action's create allows move-from."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_occupied_by_new_rejects_move_to(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position guaranteed occupied via the action's create rejects move-to."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 49
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 7
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_occupied_by_existing_rejects_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position occupied by the action's move rejects create."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 48
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_occupied_by_existing_rejects_move_to(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a position occupied by the action's move rejects another move-to."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 8
    assert all_diags[0].occupied_at.column == 48
    assert all_diags[0].occupied_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_constructor_trigger_applies_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Trigger from within a constructor applies the action's empty guarantee."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<trigger_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<inner> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos>.\n"
                "        create a particle in position<inner>.\n"
                "        create a particle in position<inner>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<inner>::action</other>::position<trigger_pos> to position<to_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.MoveFromEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("construct.dfn")
    assert (
        all_diags[0].position_name
        == "position<inner>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _CONSTRUCT, _OTHER)


def test_constructor_trigger_applies_occupied_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Trigger from within a constructor applies the action's occupied guarantee."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "construct.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct> {\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<inner> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<inner>.\n"
                "        create a particle in position<inner>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<inner>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</construct>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("construct.dfn")
    assert (
        all_diags[0].position_name == "position<inner>::action</other>::position<item>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _CONSTRUCT, _OTHER)


def test_trigger_chain_move_guarantee_empties_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain correctly applies a child move guarantee, emptying the child position."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<trigger_pos>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare>::position</x>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_create_guarantee_fills_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A trigger chain correctly applies a child create guarantee, filling the child position."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>::position</x>"
    )
    assert all_diags[0].populated_at.line == 10
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_existing_guarantee_preserves_caller_qualities(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After a trigger chain move-then-return, the particle retains its original constraint qualities."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</quality_a>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<tmp>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<trigger_pos>::position</x> to position<tmp>.\n"
                "        move the particle in position<tmp> to position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<wide> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_a>.\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<wide>.\n"
                "        move the particle in position<wide> to position<spare>::position</x>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<trigger_pos>::position</x> to position<needs_b>.\n"
                "        create a particle in position<needs_b>::position</quality_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_existing_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a child position filled by the action's move is guaranteed occupied."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<item>::position</child_q> to position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_empty_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a child position emptied by the action is guaranteed empty."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</child_q>.\n"
                "        move the particle in position<item>::position</child_q> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<item>::position</child_q> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.MoveFromEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_new_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a child position newly created by the action is guaranteed occupied."""
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        create a particle in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</x>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_empty_guarantee_deletes_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, moving a parent away guarantees its children are also empty."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>::position</child_q>.\n"
                "        move the particle in position<item> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<item>::position</child_q> to position<sink>.\n"
                "        create a particle in position<spare2>.\n"
                "        create a particle in position<spare2>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_new_guarantee_deletes_old_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, replacing a particle in a position deletes the old particle's children."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<iface> to position<_sink>.\n"
                "        create a particle in position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare_a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare_a>.\n"
                "        create a particle in position<spare_b>.\n"
                "        move the particle in position<spare> to position<local>.\n"
                "        move the particle in position<spare_a> to position<local>::position</a>.\n"
                "        move the particle in position<spare_b> to position<local>::position</b>.\n"
                "        move the particle in position<local> to position<box>::action</other>::position<iface>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<iface>::position</a> to position<sink>.\n"
                "        create a particle in position<spare_a>.\n"
                "        create a particle in position<spare_a>::position</a>.\n"
                "        create a particle in position<spare_b>.\n"
                "        create a particle in position<spare_b>::position</b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.MoveFromEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 43
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<iface>::position</a>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_child_removed_before_parent_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, removing a child then moving the parent leaves the destination child empty."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</child_q> to position<_sink>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "        create a particle in position<spare2>.\n"
                "        create a particle in position<spare2>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_parent_and_child_both_have_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, parent move and child create guarantees both apply at the destination."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "        create a particle in position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_child_guarantee_follows_parent_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a child guarantee follows its parent when the parent is moved."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</child_q>.\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_existing_guarantee_empties_origin_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, moving a parent away empties the origin's children even if the caller filled them."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<iface_return>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<iface>::position</child_q>.\n"
                "        move the particle in position<iface> to position<iface_return>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        move the particle in position<spare> to position<local>.\n"
                "        move the particle in position<spare2> to position<local>::position</child_q>.\n"
                "        move the particle in position<local> to position<box>::action</other>::position<iface>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<iface>::position</child_q> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 30
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<iface>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<iface>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_existing_guarantee_on_child_swap(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, swapping children between positions preserves each particle's qualities."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<b> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_tmp>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<a>::position</child_q> to position<_tmp>.\n"
                "        move the particle in position<b>::position</child_q> to position<a>::position</child_q>.\n"
                "        move the particle in position<_tmp> to position<b>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sa> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sb> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_a> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_b> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<spare2>.\n"
                "        create a particle in position<sa>.\n"
                "        create a particle in position<sb>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<a>.\n"
                "        move the particle in position<spare2> to position<box>::action</other>::position<b>.\n"
                "        move the particle in position<sa> to position<box>::action</other>::position<a>::position</child_q>.\n"
                "        move the particle in position<sb> to position<box>::action</other>::position<b>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<a>::position</child_q> to position<needs_b>.\n"
                "        move the particle in position<box>::action</other>::position<b>::position</child_q> to position<needs_a>.\n"
                "        create a particle in position<needs_a>::position</quality_a>.\n"
                "        create a particle in position<needs_b>::position</quality_b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_long_chain_trigger_fires_and_applies_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</outer>::position<iface>::action</inner>::position<output> to position<dest>.\n"
                "        destroy the particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_long_inner_chained_action_fills_positions_in_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        define the position<_sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos> to position<_sink>.\n"
                "        move the particle in position<box>::action</outer>::position<iface>::action</inner>::position<output> to position<dest>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)


def test_long_chain_inner_requirement_enforced_through_nested_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner creates in position<item>, requiring it empty.

    /outer triggers /inner internally. /test pre-fills the deeply nested
    position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>,
    then triggers /outer. The inner requirement that position<item> be empty
    produces an inferred-requirement-violation diagnostic.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<outer_iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<outer_iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<local>.\n"
                "        create a particle in position<local>::action</outer>::position<outer_iface>.\n"
                "        create a particle in position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>.\n"
                "        create a particle in position<local>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/outer>'"
    assert all_diags[0].required_empty is True
    assert (
        all_diags[0].position_name
        == "position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>",
            "triggered_quality_name": None,
            "line": 13,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OUTER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _OUTER,
            "triggered_quality_name": _INNER,
            "line": 11,
            "column": 30,
            "file_path": "outer.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_destroy_produces_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action destroys an interface position, the caller sees it as empty afterward."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<dest>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_destroy_prunes_children_from_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroy prunes children from the caller's perspective.

    When an action destroys an interface position, child positions filled by
    the caller are also destroyed. Trying to move from the child afterward fails.
    """
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>::position</child_q>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</other>::position<item>::position</child_q> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_retriggering_same_action_reapplies_its_guarantee_over_a_later_body_change(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering /inner fills out; the body empties out; re-triggering /inner re-fills out (the later guarantee wins), so a create there fails."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<t>.\n"
                "    define the position<out>.\n"
                "    it happens when {\n"
                "        the position<t> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<out>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<t>.\n"
                "        destroy the particle in position<box>::action</inner>::position<out>.\n"
                "        destroy the particle in position<box>::action</inner>::position<t>.\n"
                "        create a particle in position<box>::action</inner>::position<t>.\n"
                "        create a particle in position<box>::action</inner>::position<out>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diag.position_name == "position<box>::action</inner>::position<out>"
    assert diag.location.line == 16
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")


def test_two_actions_with_opposite_guarantees_on_a_shared_position_later_wins(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Triggering /emptier then /filler, which give opposite guarantees on the same implied </shared>, leaves it occupied (the later /filler wins), so a create there fails."""
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": (
                "define the potential position<my.domain.com:my_lib:/shared>.\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</shared>.\n"
                "    define the position<trigger_f>.\n"
                "    it happens when {\n"
                "        the position<trigger_f> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</shared>.\n"
                "    }\n"
                "}\n"
            ),
            "emptier.dfn": (
                "define the potential action<my.domain.com:my_lib:/emptier> {\n"
                "    it also assigns the position</shared>.\n"
                "    define the position<trigger_e>.\n"
                "    it happens when {\n"
                "        the position<trigger_e> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</shared>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</shared>.\n"
                "            it has the action</filler>.\n"
                "            it has the action</emptier>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</shared>.\n"
                "        create a particle in position<box>::action</emptier>::position<trigger_e>.\n"
                "        create a particle in position<box>::action</filler>::position<trigger_f>.\n"
                "        create a particle in position<box>::position</shared>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diag.position_name == "position<box>::position</shared>"
    assert diag.location.line == 17
    assert diag.location.column == 30
    assert diag.location.file_path == PurePosixPath("test.dfn")


_CHILD_TO_NEW_PARENT_BUG_REASON = (
    "Moving a child to a new particle and then finalizing the original parent "
    "loses the moved child's identity: the parent's guarantee sorts before the "
    "OccupiedByExisting (length-primary order) and its subtree cleanup deletes "
    "the origin child, which is only an origin (never a guarantee key) and so is "
    "never saved. The destination resolves to ERROR instead of the child."
)


@pytest.mark.xfail(strict=True, reason=_CHILD_TO_NEW_PARENT_BUG_REASON)
def test_existing_guarantee_on_child_survives_destroying_original_parent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A callee moves item::/child_q to dest::/child_q then destroys item; the moved child must still read as occupied at dest::/child_q in the caller."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<item>::position</child_q> to position<dest>::position</child_q>.\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )


@pytest.mark.xfail(strict=True, reason=_CHILD_TO_NEW_PARENT_BUG_REASON)
def test_existing_guarantee_on_child_survives_recreating_original_parent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A callee moves item::/child_q to dest::/child_q then destroys and recreates item; the moved child must still read as occupied at dest::/child_q in the caller."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<item>::position</child_q> to position<dest>::position</child_q>.\n"
                "        destroy the particle in position<item>.\n"
                "        create a particle in position<item>.\n"
                "        create a particle in position<item>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<dest>::position</child_q>"
    )
