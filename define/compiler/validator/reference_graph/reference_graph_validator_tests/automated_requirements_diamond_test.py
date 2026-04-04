# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_SHARED = "action<my.domain.com:my_lib:/shared>"

_SHARED_EMPTY_REQ = (
    "define the potential action<my.domain.com:my_lib:/shared> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in position<item>.\n"
    "    }\n"
    "}\n"
)

_ACT_B_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain dimension points where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in position<gateway>::action</shared>::position<trigger_pos>.\n"
    "    }\n"
    "}\n"
)

_ACT_C_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain dimension points where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in position<gateway>::action</shared>::position<trigger_pos>.\n"
    "    }\n"
    "}\n"
)


def test_diamond_both_paths_satisfy_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> empty (its first reference is a create).

    /test triggers /act_b and /act_c, both of which trigger /shared.
    Neither path pre-fills position<item>, so both instances of /shared
    have their EMPTY requirement satisfied.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_EMPTY_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box_b>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a dimension point in position<box_c>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_one_path_violates_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> empty.

    /test pre-fills position<item> through /act_b's path but not through
    /act_c's path. Only one ActionRequiresEmptyPositionDiagnostic appears,
    for /act_b's instance. This proves B::/shared and C::/shared are
    independent instances.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_EMPTY_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box_b>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a dimension point in position<box_c>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == _SHARED
    assert (
        all_diags[0].position_name
        == "position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_other_path_violates_empty_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> empty.

    /test pre-fills position<item> through /act_c's path but not through
    /act_b's path. Only one ActionRequiresEmptyPositionDiagnostic appears,
    for /act_c's instance. A->B->D succeeds while A->C->D fails.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_EMPTY_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box_b>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a dimension point in position<box_c>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == _SHARED
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_occupied_requirement_independent_per_path(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> occupied (first reference is a move-from).

    /act_b fills position<item> before triggering /shared — satisfying the
    OCCUPIED requirement. /act_c does NOT fill position<item> — violating
    the OCCUPIED requirement. The error is on /act_c, not on /test, because
    OCCUPIED requirements do not propagate to callers.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": (
                "define the potential action<my.domain.com:my_lib:/shared> {\n"
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
            "act_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pp>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</shared>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pp> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<gateway>::action</shared>::position<item>.\n"
                "        create a dimension point in position<gateway>::action</shared>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "act_c.dfn": (
                "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                "    define the position<pp>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</shared>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pp> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<gateway>::action</shared>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<box_b>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a dimension point in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a dimension point in position<box_c>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a dimension point in position<box_c>::action</act_c>::position<pp>.\n"
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
    assert all_diags[0].action_name == _SHARED
    assert (
        all_diags[0].position_name
        == "position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("act_c.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)
