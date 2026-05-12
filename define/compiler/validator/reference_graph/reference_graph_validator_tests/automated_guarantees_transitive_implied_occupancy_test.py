# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"

_TRANSITIVE_EDGES = {
    (_TEST, _IMPLIED),
    (_IMPLIER, _FORWARDER),
    (_FORWARDER, _IMPLIED),
}


def test_occupied_guarantee_propagates_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<output> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_empty_guarantee_propagates_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<input>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<input> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<input>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<input>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_occupied_guarantee_blocks_create_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<output>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<output>.\n"
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
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 93
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<output>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 37
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 53
    assert all_diags[0].populated_at.file_path == PurePosixPath("implied_action.dfn")
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_empty_guarantee_blocks_move_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<input>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<input> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<input>.\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<input>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</implied_action>::position<input> to position<dest>.\n"
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
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 92
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<input>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 52
    assert all_diags[0].inferred_at.file_path == PurePosixPath("implied_action.dfn")
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_occupied_implied_position_guarantee_propagates_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_pos.dfn": "define the potential position<my.domain.com:my_lib:/implied_pos>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::position</implied_pos> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_empty_implied_position_guarantee_propagates_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_pos.dfn": "define the potential position<my.domain.com:my_lib:/implied_pos>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position</implied_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</implied_pos>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::position</implied_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_occupied_implied_position_guarantee_blocks_create_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_pos.dfn": "define the potential position<my.domain.com:my_lib:/implied_pos>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::position</implied_pos>.\n"
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
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 37
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 59
    assert all_diags[0].populated_at.file_path == PurePosixPath("implied_action.dfn")
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_empty_implied_position_guarantee_blocks_move_through_transitive_implication(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_pos.dfn": "define the potential position<my.domain.com:my_lib:/implied_pos>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position</implied_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</implied_pos>.\n"
                "        create a dimension point in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::position</implied_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 74
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES
