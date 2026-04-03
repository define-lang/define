# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_POS_TEST = "position<my.domain.com:my_lib:/test>"


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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].created_at.line == 12
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("test.dfn")


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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].created_at.line == 12
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("test.dfn")
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<trigger_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<to_pos>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<trigger_pos> to position<to_pos>.\n"
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
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].created_at.line == 7
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("other.dfn")
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].created_at.line == 4
    assert all_diags[0].created_at.column == 13
    assert all_diags[0].created_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_second_trigger_cycle_after_guarantee_empties_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the action moves the trigger DP away, the trigger position is empty after trigger, allowing re-trigger."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos> to position<_sink>.\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].filled_at.line == 9
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].propagated_from_locations == []
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].filled_at.line == 10
    assert all_diags[0].filled_at.column == 55
    assert all_diags[0].filled_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].propagated_from_locations == []
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].inferred_at.line == 10
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[1].location.line == 16
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].filled_at.line == 10
    assert all_diags[1].filled_at.column == 55
    assert all_diags[1].filled_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[1].inferred_at.line == 10
    assert all_diags[1].inferred_at.column == 55
    assert all_diags[1].inferred_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[1].propagated_from_locations == []
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<dest> to position<sink>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_dp_identity_preserved_through_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After trigger, a DP moved by the action's guarantee retains its constraint qualities."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</quality_a>.\n"
                "            it has the position</quality_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<wide> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_a>.\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<wide>.\n"
                "        move the dimension point in position<wide> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<dest> to position<wide>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<item> to position<dest>.\n"
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 56
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 7
    assert all_diags[0].occupied_at.column == 37
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].created_at.line == 8
    assert all_diags[0].created_at.column == 55
    assert all_diags[0].created_at.file_path == PurePosixPath("other.dfn")
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        define the position<spare2>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 57
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 8
    assert all_diags[0].occupied_at.column == 55
    assert all_diags[0].occupied_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_position_init_trigger_applies_empty_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Trigger from a position init block applies the action's empty guarantee."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<trigger_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        define the position<to_pos>.\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position</test>::action</other>::position<trigger_pos> to position<to_pos>.\n"
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
    assert all_diags[0].location.line == 9
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position</test>::action</other>::position<trigger_pos>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)


def test_position_init_trigger_applies_occupied_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Trigger from a position init block applies the action's occupied guarantee."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</other>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</test>.\n"
                "        create a dimension point in position</test>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position</test>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "position</test>::action</other>::position<item>"
    )
    assert all_diags[0].created_at.line == 7
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _POS_TEST, _OTHER)


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
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare>::position</x>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<trigger_pos>.\n"
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
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<trigger_pos>::position</x>"
    )
    assert all_diags[0].created_at.line == 10
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_trigger_chain_existing_guarantee_preserves_caller_qualities(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """After a trigger chain move-then-return, the DP retains its original constraint qualities."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</quality_a>.\n"
                "    }\n"
                "}\n"
            ),
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<tmp>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<tmp>.\n"
                "        move the dimension point in position<tmp> to position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<wide> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_a>.\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<wide>.\n"
                "        move the dimension point in position<wide> to position<spare>::position</x>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<trigger_pos>::position</x> to position<needs_b>.\n"
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<dest>.\n"
                "        move the dimension point in position<item>::position</child_q> to position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 23
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>::position</child_q>.\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<item>::position</child_q> to position<sink>.\n"
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
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        create a dimension point in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<item>::position</child_q> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 28
    assert all_diags[0].location.column == 37
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
    """After trigger, replacing a DP in a position deletes the old DP's children."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "b.dfn": "define the potential position<my.domain.com:my_lib:/b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<iface> to position<_sink>.\n"
                "        create a dimension point in position<iface>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</a>.\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare_a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare_b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare_a>.\n"
                "        create a dimension point in position<spare_b>.\n"
                "        move the dimension point in position<spare> to position<local>.\n"
                "        move the dimension point in position<spare_a> to position<local>::position</a>.\n"
                "        move the dimension point in position<spare_b> to position<local>::position</b>.\n"
                "        move the dimension point in position<local> to position<box>::action</other>::position<iface>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<iface>::position</a> to position<sink>.\n"
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
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "        create a dimension point in position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>::position</child_q>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 20
    assert all_diags[0].location.column == 37
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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<iface_return>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<iface> to position<iface_return>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<local>.\n"
                "        move the dimension point in position<spare2> to position<local>::position</child_q>.\n"
                "        move the dimension point in position<local> to position<box>::action</other>::position<iface>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<iface>::position</child_q> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 30
    assert all_diags[0].location.column == 37
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
    """After trigger, swapping children between positions preserves each DP's qualities."""
    result = validate_project_with_reference_graph(
        {
            "child_q.dfn": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "quality_b.dfn": "define the potential position<my.domain.com:my_lib:/quality_b>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<b> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_tmp>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<a>::position</child_q> to position<_tmp>.\n"
                "        move the dimension point in position<b>::position</child_q> to position<a>::position</child_q>.\n"
                "        move the dimension point in position<_tmp> to position<b>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sa> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<sb> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_a> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_a>.\n"
                "            }\n"
                "        }\n"
                "        define the position<needs_b> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</quality_b>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        create a dimension point in position<sa>.\n"
                "        create a dimension point in position<sb>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<a>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<b>.\n"
                "        move the dimension point in position<sa> to position<box>::action</other>::position<a>::position</child_q>.\n"
                "        move the dimension point in position<sb> to position<box>::action</other>::position<b>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<a>::position</child_q> to position<needs_b>.\n"
                "        move the dimension point in position<box>::action</other>::position<b>::position</child_q> to position<needs_a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "When the caller fills a nested action chain"
        " (iface::action</inner>::trigger_pos), the inner trigger does not fire"
        " and the inner action's guarantees are not applied. The move from the"
        " guarantee-filled position fails because the position appears empty."
    ),
)
def test_long_inner_chained_action_fills_positions_in_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner creates in position<output>, guaranteeing it occupied.

    /outer triggers /inner internally. When /test fills the nested trigger position
    (position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>),
    the inner trigger should fire at /test's level, applying /inner's guarantee
    so that position<output> is occupied. /test then moves from position<output>,
    which should succeed because the guarantee filled it.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        define the position<_sink>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos> to position<_sink>.\n"
                "        move the dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<output> to position<dest>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
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
    produces ActionRequiresEmptyPositionDiagnostic.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<outer_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<outer_iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</outer>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::action</outer>::position<outer_iface>.\n"
                "        create a dimension point in position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<local>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name
        == "position<local>::action</outer>::position<outer_iface>::action</inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)
