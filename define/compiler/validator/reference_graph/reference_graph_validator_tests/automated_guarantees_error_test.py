# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_action_calls

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"


def test_error_interface_position_stays_error_after_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An interface position with error state from conflicting moves stays error after trigger."""
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
                "        define the position<src>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<src>.\n"
                "        move the particle in position<src> to position<box>::action</other>::position<item>.\n"
                "        move the particle in position<src> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].position_name == "position<src>"
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 47
    assert all_diags[1].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 14
    assert all_diags[1].occupied_at.column == 47
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in error state, creating after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<sink>.\n"
                "        move the particle in position<item> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in error state, moving from it after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<sink>.\n"
                "        move the particle in position<item> to position<sink2>.\n"
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in error state, moving to it after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
                "        move the particle in position<item> to position<sink>.\n"
                "        move the particle in position<item> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_chain_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error guarantee through a trigger chain suppresses create diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_chain_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error guarantee through a trigger chain suppresses move-from diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink2>.\n"
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
                "        move the particle in position<box>::action</other>::position<trigger_pos>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_error_chain_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error guarantee through a trigger chain suppresses move-to diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<trigger_pos>::position</x>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the particle in position<trigger_pos>::position</x> to position<sink2>.\n"
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
                "        move the particle in position<spare> to position<box>::action</other>::position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_error_from_move_to_occupied_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving to an already-occupied interface position makes the guarantee error but reports the internal error."""
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
                "        define the position<extra>.\n"
                "        create a particle in position<extra>.\n"
                "        move the particle in position<extra> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 49
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_error_from_constraint_violation_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A constraint violation on an interface position makes the guarantee error but reports the violation."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</quality_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<unconstrained>.\n"
                "        create a particle in position<unconstrained>.\n"
                "        move the particle in position<unconstrained> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 57
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_error_propagation_from_local_to_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error state on a local position propagates to an interface position when the action moves it there."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        define the position<sink>.\n"
                "        create a particle in position<local>.\n"
                "        move the particle in position<local> to position<sink>.\n"
                "        move the particle in position<local> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_error_from_prefix_move_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving an interface position particle into one of its own child positions reports MoveIntoDefiningPositionDiagnostic."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<tp>.\n"
                "    it happens when {\n"
                "        the position<tp> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential position<my.domain.com:my_lib:/mid> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</inner>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</mid>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<iface>.\n"
                "        move the particle in position<iface> to position<iface>::position</mid>::action</inner>::position<tp>.\n"
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
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</outer>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</outer>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 66
    assert_action_calls(result.action_call_graph, _TEST, _OUTER)


def test_unknown_global_chain_start_treats_action_guarantees_as_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An unknown global chain start treats all action guarantees as error."""
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
                "        create a particle in action</other>::position<trigger_pos>.\n"
                "        create a particle in action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert isinstance(all_diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].source_global_name == "action</other>"
    assert all_diags[1].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].location.line == 7


def test_post_trigger_error_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error state on a child position from conflicting moves allows creating in it after trigger."""
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
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item>::position</child_q> to position<_sink>.\n"
                "        move the particle in position<item>::position</child_q> to position<_sink2>.\n"
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
                "        create a particle in position<box>::action</other>::position<item>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_existing_guarantee_error_origin_with_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Error state on a parent position allows creating in a child at the destination after trigger."""
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
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<_sink>.\n"
                "        move the particle in position<item> to position<_sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 30
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_prefills_child_without_parent_then_triggers(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Caller pre-fills a child interface position without the parent, then triggers.

    The parent check fires for the child create, marking it error.
    The subsequent trigger and guarantee application handle the
    error state gracefully with no spurious errors.
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
                "        create a particle in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert (
        all_diags[0].position_name
        == "position<box>::action</other>::position<item>::position</child_q>"
    )
    assert (
        all_diags[0].parent_position_name
        == "position<box>::action</other>::position<item>"
    )
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_action_creates_child_but_caller_omits_parent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Action's body creates a particle in both parent and child interface positions.

    The caller doesn't fill position<item> or its child — the action
    fills them internally, generating OccupiedByNew guarantees for both.
    The guarantee application should succeed even though the caller
    never set up the parent, because both are created by the action.
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
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 0
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_swap_guarantee_both_positions_unfilled(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Swapping two interface positions when the caller fills neither.

    Both positions get OCCUPIED requirements. When guarantees apply,
    each OccupiedByExisting tries to read its origin (the other
    position), which was never filled. Both should end up error.
    Subsequent operations on both positions are silently allowed.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<tmp>.\n"
                "        move the particle in position<a> to position<tmp>.\n"
                "        move the particle in position<b> to position<a>.\n"
                "        move the particle in position<tmp> to position<b>.\n"
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
                "        create a particle in position<box>::action</other>::position<a>.\n"
                "        create a particle in position<box>::action</other>::position<a>.\n"
                "        create a particle in position<box>::action</other>::position<b>.\n"
                "        create a particle in position<box>::action</other>::position<b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<a>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
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
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[1].required_empty is False
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
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
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_swap_guarantee_one_position_unfilled(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Swapping two interface positions when the caller fills only one.

    Only position<b> is unfilled. After the swap, position<a> should
    be error (its origin position<b> was never filled) and
    position<b> should contain what was in position<a>.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<tmp>.\n"
                "        move the particle in position<a> to position<tmp>.\n"
                "        move the particle in position<b> to position<a>.\n"
                "        move the particle in position<tmp> to position<b>.\n"
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
                "        move the particle in position<spare> to position<box>::action</other>::position<a>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<a>.\n"
                "        create a particle in position<box>::action</other>::position<b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 15,
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
    # position<b> is now occupied: the swap moved position<a>'s particle there.
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 17
    assert all_diags[1].location.end_column == 72
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert all_diags[1].populated_at.line == 11
    assert all_diags[1].populated_at.column == 47
    assert all_diags[1].populated_at.end_line == 11
    assert all_diags[1].populated_at.end_column == 58
    assert all_diags[1].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_each_unfilled_required_parent_independently_makes_caller_position_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's body touches children of two distinct interface positions, and the caller fills neither, the caller's view of *both* positions should be error afterwards.

    Subsequent operations on either are silently allowed rather than
    failing as if the position were empty.
    """
    result = validate_project_with_reference_graph(
        {
            "c1.dfn": "define the potential position<my.domain.com:my_lib:/c1>.\n",
            "c2.dfn": "define the potential position<my.domain.com:my_lib:/c2>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</c1>.\n"
                "        }\n"
                "    }\n"
                "    define the position<b> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</c2>.\n"
                "        }\n"
                "    }\n"
                "    define the position<sink_a>.\n"
                "    define the position<sink_b>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<a>::position</c1> to position<sink_a>.\n"
                "        move the particle in position<b>::position</c2> to position<sink_b>.\n"
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
                "        destroy the particle in position<box>::action</other>::position<a>.\n"
                "        destroy the particle in position<box>::action</other>::position<b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 4
    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<a>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 12
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[1].required_empty is False
    assert (
        all_diags[1].position_name
        == "position<box>::action</other>::position<a>::position</c1>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 18,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[2], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[2].location.line == 12
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.end_line == 12
    assert all_diags[2].location.end_column == 82
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[2].required_empty is False
    assert all_diags[2].position_name == "position<box>::action</other>::position<b>"
    assert_propagation_chain(
        all_diags[2],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "other.dfn",
        },
    )
    assert isinstance(all_diags[3], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[3].location.line == 12
    assert all_diags[3].location.column == 30
    assert all_diags[3].location.end_line == 12
    assert all_diags[3].location.end_column == 82
    assert all_diags[3].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[3].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[3].required_empty is False
    assert (
        all_diags[3].position_name
        == "position<box>::action</other>::position<b>::position</c2>"
    )
    assert_propagation_chain(
        all_diags[3],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 19,
            "column": 30,
            "file_path": "other.dfn",
        },
    )


def test_move_from_emptied_origin_leaves_destination_error_in_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the caller destroys a particle before triggering an action that moves from that same position, the destination position should be treated as error.

    The caller cannot know whether the action actually moved anything,
    so further operations on the destination are silently allowed.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<dst>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<src> to position<dst>.\n"
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
                "        create a particle in position<box>::action</other>::position<src>.\n"
                "        destroy the particle in position<box>::action</other>::position<src>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::action</other>::position<dst>.\n"
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
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<src>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _TEST,
            "triggered_quality_name": _OTHER,
            "line": 14,
            "column": 30,
            "file_path": "test.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _OTHER,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )


def test_occupied_by_existing_destination_the_caller_filled_becomes_error(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the caller has already put a particle in the position a triggered action moves a particle to, and never put one in the position it moves from, that position becomes error, so creating in it afterward is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<dst>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<src> to position<dst>.\n"
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
                "        create a particle in position<box>::action</other>::position<dst>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</other>::position<dst>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2

    assert isinstance(all_diags[0], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[0].required_empty is False
    assert all_diags[0].position_name == "position<box>::action</other>::position<src>"
    assert_propagation_chain(
        all_diags[0],
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
            "line": 8,
            "column": 30,
            "file_path": "other.dfn",
        },
    )

    assert isinstance(all_diags[1], diagnostics.InferredRequirementViolationDiagnostic)
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 13
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].runner_description == "'action<my.domain.com:my_lib:/other>'"
    assert all_diags[1].required_empty is True
    assert all_diags[1].position_name == "position<box>::action</other>::position<dst>"
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.FILL_SITE,
            "enclosing_quality_name": "position<box>::action</other>::position<dst>",
            "triggered_quality_name": None,
            "line": 12,
            "column": 30,
            "file_path": "test.dfn",
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
            "line": 8,
            "column": 47,
            "file_path": "other.dfn",
        },
    )


def test_swap_propagates_prior_error_state_from_origin_to_destination(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When the caller has made one of two swap targets error before triggering the swap, the other target should also be error after the swap.

    The swap moves whatever was in the error position into the other,
    and since the caller cannot know what arrived there, subsequent
    operations on the destination are silently allowed.
    """
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a>.\n"
                "    define the position<b>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_tmp>.\n"
                "        move the particle in position<a> to position<_tmp>.\n"
                "        move the particle in position<b> to position<a>.\n"
                "        move the particle in position<_tmp> to position<b>.\n"
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
                "        define the position<empty_src>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</other>::position<a>.\n"
                "        move the particle in position<empty_src> to position<box>::action</other>::position<a>.\n"
                "        create a particle in position<box>::action</other>::position<b>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::action</other>::position<b>.\n"
                "        destroy the particle in position<box>::action</other>::position<b>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 49
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<empty_src>"
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 53
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 95
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</other>::position<a>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 13
    assert all_diags[1].occupied_at.column == 30
    assert all_diags[1].occupied_at.end_line == 13
    assert all_diags[1].occupied_at.end_column == 72
    assert all_diags[1].occupied_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)
