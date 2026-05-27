# pyright: reportUnusedCallResult=false

# This file only covers OCCUPIED-state propagation. EMPTY-state propagation
# through position init blocks is structurally impossible to observe: an init
# block on /p fires when the caller creates a particle with /p as a
# quality, so any EMPTY requirement is only observed directly by the creator,
# instantly at the moment of creation.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph import action_contract
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)

_INNER = "action<my.domain.com:my_lib:/inner>"
_IMPLIED_ACTION = "action<my.domain.com:my_lib:/implied_action>"
_P = "position<my.domain.com:my_lib:/p>"
_OUTER_P = "position<my.domain.com:my_lib:/outer_p>"
_INNER_P = "position<my.domain.com:my_lib:/inner_p>"


def test_init_block_occupied_propagates_to_action_caller_via_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</p>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _INNER
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<iface>::position</q>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _P,
            "line": 11,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_propagates_via_implied_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_pos.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied_pos> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</implied_pos>.\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _INNER
    assert (
        all_diags[0].position_name
        == "position<box>::position</implied_pos>::position</q>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _P,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_propagates_via_implied_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "carrier.dfn": (
                "define the potential position<my.domain.com:my_lib:/carrier> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</carrier>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</carrier>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _INNER
    assert (
        all_diags[0].position_name == "position<box>::position</carrier>::position</q>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _IMPLIED_ACTION,
            "line": 7,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _IMPLIED_ACTION,
            "triggered_quality_name": _P,
            "line": 7,
            "column": 30,
            "file_path": "implied_action.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_init_block_occupied_propagates_from_init_block_to_init_block(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "r.dfn": "define the potential position<my.domain.com:my_lib:/r>.\n",
            "inner_p.dfn": (
                "define the potential position<my.domain.com:my_lib:/inner_p> {\n"
                "    it also assigns the position</r>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</r>.\n"
                "    }\n"
                "}\n"
            ),
            "something.dfn": (
                "define the potential position<my.domain.com:my_lib:/something> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</inner_p>.\n"
                "    }\n"
                "}\n"
            ),
            "outer_p.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer_p> {\n"
                "    it also assigns the position</something>.\n"
                "    after it is assigned {\n"
                "        create a particle in position</something>.\n"
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
                "                it has the position</outer_p>.\n"
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
        all_diags[0], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert all_diags[0].init_block_position_name == _OUTER_P
    assert (
        all_diags[0].position_name
        == "position<box>::position</something>::position</r>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _OUTER_P,
            "triggered_quality_name": _INNER_P,
            "line": 4,
            "column": 30,
            "file_path": "outer_p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER_P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 33,
            "file_path": "inner_p.dfn",
        },
    )


def test_init_block_occupied_propagates_via_local_with_parent_from_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "box_target.dfn": (
                "define the potential position<my.domain.com:my_lib:/box_target> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain particles where {\n"
                "            it has the position</box_target>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</box_target>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<iface> to position<box>.\n"
                "        create a particle in position<box>::position</box_target>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<outer_box> {\n"
                "            it may only contain particles where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<outer_box>.\n"
                "        create a particle in position<outer_box>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 88
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _INNER
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</inner>::position<iface>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": None,
            "line": 16,
            "column": 30,
            "file_path": "inner.dfn",
        },
    )
    assert isinstance(
        all_diags[1],
        diagnostics.ActionRequiresOccupiedPositionDiagnostic,
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 12
    assert all_diags[1].location.end_column == 88
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == _INNER
    assert (
        all_diags[1].position_name
        == "position<outer_box>::action</inner>::position<iface>::position</box_target>::position</q>"
    )
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.INIT_BLOCK_TRIGGER,
            "enclosing_quality_name": _INNER,
            "triggered_quality_name": _P,
            "line": 17,
            "column": 30,
            "file_path": "inner.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _P,
            "triggered_quality_name": None,
            "line": 4,
            "column": 33,
            "file_path": "p.dfn",
        },
    )


def test_action_occupied_requirement_for_interface_position_propagates_via_init_block_implied_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    after it is assigned {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the position</p>.\n"
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
        all_diags[0], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert all_diags[0].init_block_position_name == _P
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<item>"
    )
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _P,
            "triggered_quality_name": _IMPLIED_ACTION,
            "line": 4,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _IMPLIED_ACTION,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )


def test_action_occupied_requirement_on_implied_position_propagates_via_init_block_via_implied_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q.dfn": "define the potential position<my.domain.com:my_lib:/q>.\n",
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</q>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    after it is assigned {\n"
                "        create a particle in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the position</p>.\n"
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
        all_diags[0], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 43
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert all_diags[0].init_block_position_name == _P
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _P,
            "triggered_quality_name": _IMPLIED_ACTION,
            "line": 4,
            "column": 30,
            "file_path": "p.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _IMPLIED_ACTION,
            "triggered_quality_name": None,
            "line": 7,
            "column": 33,
            "file_path": "implied_action.dfn",
        },
    )
