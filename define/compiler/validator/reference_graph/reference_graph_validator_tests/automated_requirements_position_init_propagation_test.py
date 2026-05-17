# pyright: reportUnusedCallResult=false

# This file only covers OCCUPIED-state propagation. EMPTY-state propagation
# through position init blocks is structurally impossible to observe: an init
# block on /p fires when the caller creates a dimension point with /p as a
# quality, so any EMPTY requirement is only observed directly by the creator,
# instantly at the moment of creation.

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)


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
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</p>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 89
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].create_target_name
        == "position<box>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[0].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<iface>::position</q>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 11
    assert all_diags[0].inferred_at.end_column == 52
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</q>",
            "line": 4,
            "column": 40,
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
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_pos.dfn": (
                "define the potential position<my.domain.com:my_lib:/implied_pos> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied_pos>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied_pos>.\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 89
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].create_target_name
        == "position<box>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[0].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        all_diags[0].position_name
        == "position<box>::position</implied_pos>::position</q>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 7
    assert all_diags[0].inferred_at.end_column == 59
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</q>",
            "line": 4,
            "column": 40,
            "file_path": "p.dfn",
        },
    )


@pytest.mark.xfail(
    raises=KeyError,
    strict=True,
    reason=(
        "execute_assume_occupied on a propagated chain with non-action"
        " intermediate positions hits a missing trie parent —"
        " _ensure_action_parent only auto-creates intermediate action nodes."
    ),
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
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "carrier.dfn": (
                "define the potential position<my.domain.com:my_lib:/carrier> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    it also assigns the position</carrier>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</carrier>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<trigger_pos>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 89
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].create_target_name
        == "position<box>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[0].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        all_diags[0].position_name == "position<box>::position</carrier>::position</q>"
    )
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</carrier>",
            "line": 7,
            "column": 37,
            "file_path": "implied_action.dfn",
        },
        {
            "full_typed_name": "position</q>",
            "line": 4,
            "column": 40,
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
                "        destroy the dimension point in position</r>.\n"
                "    }\n"
                "}\n"
            ),
            "something.dfn": (
                "define the potential position<my.domain.com:my_lib:/something> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</inner_p>.\n"
                "    }\n"
                "}\n"
            ),
            "outer_p.dfn": (
                "define the potential position<my.domain.com:my_lib:/outer_p> {\n"
                "    it also assigns the position</something>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</something>.\n"
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
                "                it has the position</outer_p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
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
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert (
        all_diags[0].init_block_position_name
        == "position<my.domain.com:my_lib:/inner_p>"
    )
    assert (
        all_diags[0].position_name
        == "position<box>::position</something>::position</r>"
    )
    assert all_diags[0].inferred_at.line == 4
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 4
    assert all_diags[0].inferred_at.end_column == 57
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer_p.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</r>",
            "line": 4,
            "column": 40,
            "file_path": "inner_p.dfn",
        },
    )


@pytest.mark.xfail(
    raises=KeyError,
    strict=True,
    reason=(
        "execute_assume_occupied on a chain rewritten via "
        "replace_parent_position_with_prefix hits a missing trie intermediate: "
        "position-typed intermediates aren't auto-created the way action ones "
        "are by _ensure_action_parent. Pre-existing tracker limitation."
    ),
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
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "box_target.dfn": (
                "define the potential position<my.domain.com:my_lib:/box_target> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</p>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</box_target>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</box_target>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<iface> to position<box>.\n"
                "        create a dimension point in position<box>::position</box_target>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<outer_box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<outer_box>.\n"
                "        create a dimension point in position<outer_box>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 95
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name
        == "position<outer_box>::action</inner>::position<iface>"
    )
    assert all_diags[0].inferred_at.line == 16
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 16
    assert all_diags[0].inferred_at.end_column == 52
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert isinstance(
        all_diags[1],
        diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic,
    )
    assert all_diags[1].location.line == 12
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 12
    assert all_diags[1].location.end_column == 95
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[1].create_target_name
        == "position<outer_box>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[1].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        all_diags[1].position_name
        == "position<outer_box>::action</inner>::position<iface>::position</box_target>::position</q>"
    )
    assert all_diags[1].inferred_at.line == 17
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.end_line == 17
    assert all_diags[1].inferred_at.end_column == 74
    assert all_diags[1].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "full_typed_name": "position</q>",
            "line": 4,
            "column": 40,
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
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
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/implied_action>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<item>"
    )
    assert all_diags[0].inferred_at.file_path == PurePosixPath("p.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<item>",
            "line": 7,
            "column": 40,
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
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        destroy the dimension point in position</q>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
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
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 11
    assert all_diags[0].location.end_column == 50
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/implied_action>"
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert all_diags[0].inferred_at.file_path == PurePosixPath("p.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position</q>",
            "line": 7,
            "column": 40,
            "file_path": "implied_action.dfn",
        },
    )
