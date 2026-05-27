# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<output> to position<sink>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<input> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<input>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</implied_action>::position<input>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<output>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a particle in position<box>::action</implied_action>::position<output>.\n"
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
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 86
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<output>"
    )
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 46
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position<input> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<input>.\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<input>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::action</implied_action>::position<input> to position<dest>.\n"
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
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 85
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<input>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 45
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::position</implied_pos> to position<sink>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</implied_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</implied_pos>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied_pos>.\n"
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
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
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        create a particle in position<box>::position</implied_pos>.\n"
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
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 67
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 7
    assert all_diags[0].populated_at.end_column == 52
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
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</implied_pos> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "forwarder.dfn": (
                "define the potential action<my.domain.com:my_lib:/forwarder> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</forwarder>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</forwarder>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</implied_pos>.\n"
                "        create a particle in position<box>::action</implied_action>::position<trigger_pos>.\n"
                "        move the particle in position<box>::position</implied_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 15
    assert all_diags[0].location.end_column == 67
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::position</implied_pos>"
    assert result.action_call_graph.unique_edges() == _TRANSITIVE_EDGES


def test_implied_position_self_create_init_block_fires_on_caller_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "first_implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/first_implied> {\n"
                "    after it is assigned {\n"
                "        create a particle in position</first_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</first_implied>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</first_implied>.\n"
                "        destroy the particle in position</first_implied>.\n"
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
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</first_implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    first = all_diags[0]
    assert isinstance(
        first, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert first.create_target_name == "position<box>"
    assert first.init_block_position_name == "position<my.domain.com:my_lib:/implier>"
    assert first.position_name == "position<box>::position</first_implied>"
    assert first.location.line == 11
    assert first.location.column == 30
    assert first.location.end_line == 11
    assert first.location.end_column == 43
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.filled_at.line == 3
    assert first.filled_at.column == 30
    assert first.filled_at.end_line == 3
    assert first.filled_at.end_column == 54
    assert first.filled_at.file_path == PurePosixPath("first_implied.dfn")
    assert_propagation_chain(
        first,
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/implier>",
            "triggered_quality_name": None,
            "line": 4,
            "column": 30,
            "file_path": "implier.dfn",
        },
    )
    second = all_diags[1]
    assert isinstance(second, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert second.location.line == 12
    assert second.location.column == 30
    assert second.location.end_line == 12
    assert second.location.end_column == 69
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.position_name == "position<box>::position</first_implied>"
    assert second.populated_at.line == 3
    assert second.populated_at.column == 30
    assert second.populated_at.end_line == 3
    assert second.populated_at.end_column == 54
    assert second.populated_at.file_path == PurePosixPath("first_implied.dfn")


def test_transitively_implied_position_self_create_init_block_fires_on_caller_create(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "second_implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/second_implied> {\n"
                "    after it is assigned {\n"
                "        create a particle in position</second_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "first_implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/first_implied> {\n"
                "    it also assigns the position</second_implied>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</second_implied>.\n"
                "        destroy the particle in position</second_implied>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential position<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the position</first_implied>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</first_implied>.\n"
                "        destroy the particle in position</first_implied>.\n"
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
                "                it has the position</implier>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</second_implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    first = all_diags[0]
    assert isinstance(
        first, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert first.create_target_name == "position<box>"
    assert (
        first.init_block_position_name
        == "position<my.domain.com:my_lib:/first_implied>"
    )
    assert first.position_name == "position<box>::position</second_implied>"
    assert first.location.line == 11
    assert first.location.column == 30
    assert first.location.end_line == 11
    assert first.location.end_column == 43
    assert first.location.file_path == PurePosixPath("test.dfn")
    assert first.filled_at.line == 3
    assert first.filled_at.column == 30
    assert first.filled_at.end_line == 3
    assert first.filled_at.end_column == 55
    assert first.filled_at.file_path == PurePosixPath("second_implied.dfn")
    assert_propagation_chain(
        first,
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": "position<my.domain.com:my_lib:/first_implied>",
            "triggered_quality_name": None,
            "line": 4,
            "column": 30,
            "file_path": "first_implied.dfn",
        },
    )
    second = all_diags[1]
    assert isinstance(second, diagnostics.CreateInOccupiedPositionDiagnostic)
    assert second.location.line == 12
    assert second.location.column == 30
    assert second.location.end_line == 12
    assert second.location.end_column == 70
    assert second.location.file_path == PurePosixPath("test.dfn")
    assert second.position_name == "position<box>::position</second_implied>"
    assert second.populated_at.line == 3
    assert second.populated_at.column == 30
    assert second.populated_at.end_line == 3
    assert second.populated_at.end_column == 55
    assert second.populated_at.file_path == PurePosixPath("second_implied.dfn")


def test_inner_action_guarantee_through_implied_action_chain_attaches_to_full_caller_prefix(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An action whose body creates a particle at a chain that starts with an implied action quality (action</nested>::position<iface>::position</x>) records a guarantee on that chain.

    When such an action is fired from a caller that reaches it through a
    long position prefix, the resulting tracker key should include the
    full caller-side prefix.

    Filling the same fully-qualified position from the caller after the
    trigger should fail with a CreateInOccupied diagnostic.
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "nested.dfn": (
                "define the potential action<my.domain.com:my_lib:/nested> {\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the action</nested>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</nested>::position<iface>.\n"
                "        create a particle in action</nested>::position<iface>::position</x>.\n"
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
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<host> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</mid>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<host>.\n"
                "        create a particle in position<host>::position</mid>.\n"
                "        create a particle in position<host>::position</mid>::action</inner>::position<trigger_pos>.\n"
                "        create a particle in position<host>::position</mid>::action</nested>::position<iface>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 108
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<host>::position</mid>::action</nested>::position<iface>::position</x>"
    )
    assert all_diags[0].populated_at.line == 8
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 8
    assert all_diags[0].populated_at.end_column == 76
    assert all_diags[0].populated_at.file_path == PurePosixPath("inner.dfn")


def test_sibling_action_guarantee_and_requirement_share_implied_position_key(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied>.\n"
            ),
            "filler.dfn": (
                "define the potential action<my.domain.com:my_lib:/filler> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger>.\n"
                "    it happens when {\n"
                "        the position<trigger> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "consumer.dfn": (
                "define the potential action<my.domain.com:my_lib:/consumer> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<trigger> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position</implied> to position<sink>.\n"
                "        create a particle in position</implied>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</filler>.\n"
                "    it also assigns the action</consumer>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</filler>::position<trigger>.\n"
                "        create a particle in action</consumer>::position<trigger>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
