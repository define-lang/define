# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import conftest, diagnostics
from define.compiler.validator.reference_graph.reference_graph_validator_tests.test_helpers import (
    assert_propagation_chain,
)
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_POS_TEST = "position<my.domain.com:my_lib:/test>"


_IMPLIED_ACTION_NOOP = (
    "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
    "    define the position<trigger_pos>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a dimension point.\n"
    "    } and it does {\n"
    "        define the position<_noop>.\n"
    "        create a dimension point in position<_noop>.\n"
    "    }\n"
    "}\n"
)


def test_action_triggers_implied_action_directly(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": _IMPLIED_ACTION_NOOP,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _IMPLIED)}


def test_action_triggers_implied_action_via_move(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": _IMPLIED_ACTION_NOOP,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<tmp>.\n"
                "        create a dimension point in position<tmp>.\n"
                "        move the dimension point in position<tmp> to action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _IMPLIED)}


def test_position_init_triggers_implied_action(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": _IMPLIED_ACTION_NOOP,
            "test.dfn": (
                "define the potential position<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    after it is assigned {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_POS_TEST, _IMPLIED)}


def test_implied_action_iface_requirement_propagates_to_caller(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<extra>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<extra> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
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
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_action>::position<extra>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<extra>",
            "line": 8,
            "column": 37,
            "file_path": "implied_action.dfn",
        },
    )
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _MIDDLE),
        (_MIDDLE, _IMPLIED),
    }


def test_implied_action_with_iface_routing_to_inner_action_propagates(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    """An inner action reached through an interface position of an implied action still has its requirements propagated up the call chain."""
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<extra>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<extra> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_outer> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</implied_outer>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_outer>::position<iface>.\n"
                "        create a dimension point in action</implied_outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_outer>::position<iface>::action</inner>::position<extra>"
    )
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<extra>",
            "line": 8,
            "column": 37,
            "file_path": "inner.dfn",
        },
    )


def test_inner_action_through_implied_action_iface_propagates_when_intermediate_only_triggers(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<extra>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<extra> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "implied_outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_outer> {\n"
                "    define the position<run>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    it also assigns the action</implied_outer>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "                it has the action</middle>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</implied_outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</middle>::position<run>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _MIDDLE
    assert (
        all_diags[0].position_name
        == "position<box>::action</implied_outer>::position<iface>::action</inner>::position<extra>"
    )
    assert all_diags[0].inferred_at.line == 7
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "full_typed_name": "position<extra>",
            "line": 8,
            "column": 37,
            "file_path": "inner.dfn",
        },
    )


def test_caller_triggers_action_implied_by_constraint(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": (
                "define the potential action<my.domain.com:my_lib:/implied_action> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<spare_iface>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "implier.dfn": (
                "define the potential action<my.domain.com:my_lib:/implier> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<spare_iface>.\n"
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
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _IMPLIED)}


def test_implied_action_guarantees_propagate_to_caller(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
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
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the action</implied_action>.\n"
                "    define the position<run>.\n"
                "    define the position<sink>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</implied_action>::position<trigger_pos>.\n"
                "        move the dimension point in action</implied_action>::position<output> to position<sink>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {(_TEST, _IMPLIED)}


def test_transitive_implication_triggers_action(
    validate_project_with_reference_graph: conftest.ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied_action.dfn": _IMPLIED_ACTION_NOOP,
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
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.unique_edges() == {
        (_TEST, _IMPLIED),
        (_IMPLIER, _FORWARDER),
        (_FORWARDER, _IMPLIED),
    }
