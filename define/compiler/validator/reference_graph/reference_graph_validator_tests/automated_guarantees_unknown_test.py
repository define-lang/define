# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_action_calls

_TEST = "action<my.domain.com:my_lib:/test>"
_OTHER = "action<my.domain.com:my_lib:/other>"
_OUTER = "action<my.domain.com:my_lib:/outer>"


def test_unknown_interface_position_stays_unknown_after_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An interface position with unknown state from conflicting moves stays unknown after trigger."""
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
                "        define the position<src>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<src> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
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
    assert all_diags[0].location.column == 37
    assert all_diags[0].position_name == "position<src>"
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 54
    assert all_diags[1].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 14
    assert all_diags[1].occupied_at.column == 54
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in unknown state, creating after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in unknown state, moving from it after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """When an action's guarantee results in unknown state, moving to it after trigger is silently allowed."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_chain_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown guarantee through a trigger chain suppresses create diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_chain_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown guarantee through a trigger chain suppresses move-from diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
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
                "        move the dimension point in position<box>::action</other>::position<trigger_pos>::position</x> to position<dest>.\n"
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
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_unknown_chain_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown guarantee through a trigger chain suppresses move-to diagnostics."""
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
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
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
                "        move the dimension point in position<spare> to position<box>::action</other>::position<trigger_pos>::position</x>.\n"
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
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_unknown_from_move_to_occupied_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving to an already-occupied interface position makes the guarantee unknown but reports the internal error."""
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
                "        define the position<extra>.\n"
                "        create a dimension point in position<extra>.\n"
                "        move the dimension point in position<extra> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 56
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_unknown_from_constraint_violation_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A constraint violation on an interface position makes the guarantee unknown but reports the violation."""
    result = validate_project_with_reference_graph(
        {
            "quality_a.dfn": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</quality_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<unconstrained>.\n"
                "        create a dimension point in position<unconstrained>.\n"
                "        move the dimension point in position<unconstrained> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 64
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_unknown_propagation_from_local_to_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown state on a local position propagates to an interface position when the action moves it there."""
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position<sink>.\n"
                "        move the dimension point in position<local> to position<item>.\n"
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
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_unknown_from_prefix_move_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Moving an interface position DP into one of its own child positions reports MoveIntoDefiningPositionDiagnostic."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<tp>.\n"
                "    it happens when {\n"
                "        the position<tp> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.dfn": (
                "define the potential position<my.domain.com:my_lib:/mid> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</inner>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</mid>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>.\n"
                "        move the dimension point in position<iface> to position<iface>::position</mid>::action</inner>::position<tp>.\n"
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
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
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
    assert all_diags[0].location.column == 73
    assert_action_calls(result.action_call_graph, _TEST, _OUTER)


def test_unknown_global_chain_start_treats_action_guarantees_as_unknown(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An unknown global chain start treats all action guarantees as unknown."""
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
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "        create a dimension point in action</other>::position<item>.\n"
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


def test_post_trigger_unknown_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown state on a child position from conflicting moves allows creating in it after trigger."""
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
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink>.\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink2>.\n"
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
                "        create a dimension point in position<box>::action</other>::position<item>::position</child_q>.\n"
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
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_post_trigger_existing_guarantee_unknown_origin_with_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Unknown state on a parent position allows creating in a child at the destination after trigger."""
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
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<_sink2>.\n"
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
                "        create a dimension point in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
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
    assert all_diags[0].location.column == 37
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_caller_prefills_child_without_parent_then_triggers(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Caller pre-fills a child interface position without the parent, then triggers.

    The parent check fires for the child create, marking it unknown.
    The subsequent trigger and guarantee application handle the
    unknown state gracefully with no spurious errors.
    """
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
                "        create a dimension point in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.column == 37
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
    """Action's body creates a DP in both parent and child interface positions.

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
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        create a dimension point in position<item>::position</child_q>.\n"
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
    position), which was never filled. Both should end up unknown.
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<tmp>.\n"
                "        move the dimension point in position<a> to position<tmp>.\n"
                "        move the dimension point in position<b> to position<a>.\n"
                "        move the dimension point in position<tmp> to position<b>.\n"
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
                "        create a dimension point in position<box>::action</other>::position<a>.\n"
                "        create a dimension point in position<box>::action</other>::position<a>.\n"
                "        create a dimension point in position<box>::action</other>::position<b>.\n"
                "        create a dimension point in position<box>::action</other>::position<b>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].position_name == "position<box>::action</other>::position<a>"
    assert all_diags[0].inferred_at.line == 9
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert isinstance(
        all_diags[1], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert all_diags[1].inferred_at.line == 10
    assert all_diags[1].inferred_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[1].propagated_from_locations == []
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)


def test_swap_guarantee_one_position_unfilled(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Swapping two interface positions when the caller fills only one.

    Only position<b> is unfilled. After the swap, position<a> should
    be unknown (its origin position<b> was never filled) and
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<tmp>.\n"
                "        move the dimension point in position<a> to position<tmp>.\n"
                "        move the dimension point in position<b> to position<a>.\n"
                "        move the dimension point in position<tmp> to position<b>.\n"
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
                "        move the dimension point in position<spare> to position<box>::action</other>::position<a>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<a>.\n"
                "        create a dimension point in position<box>::action</other>::position<b>.\n"
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
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].position_name == "position<box>::action</other>::position<b>"
    assert all_diags[0].inferred_at.line == 10
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")
    assert all_diags[0].propagated_from_locations == []
    # position<b> is now occupied: the swap moved position<a>'s DP there.
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</other>::position<b>"
    assert all_diags[1].populated_at.line == 11
    assert all_diags[1].populated_at.column == 54
    assert all_diags[1].populated_at.file_path == PurePosixPath("other.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OTHER)
