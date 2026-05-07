# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

import pytest

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_IMPLIED = "action<my.domain.com:my_lib:/implied_action>"
_IMPLIER = "action<my.domain.com:my_lib:/implier>"
_FORWARDER = "action<my.domain.com:my_lib:/forwarder>"
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


def test_caller_triggering_implied_action_violates_inner_requirement(
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 7
    assert all_diags[0].location.end_column == 83
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == _IMPLIED
    assert all_diags[0].position_name == "action</implied_action>::position<extra>"
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 52
    assert all_diags[0].inferred_at.file_path == PurePosixPath("implied_action.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert result.action_call_graph.unique_edges() == {(_TEST, _IMPLIED)}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Requirements are not yet inferred for implied-action iface positions"
        " whose state was filled by a prior internal trigger."
    ),
)
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
