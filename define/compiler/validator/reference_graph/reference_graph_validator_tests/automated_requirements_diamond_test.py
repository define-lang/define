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
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_ACT_B = "action<my.domain.com:my_lib:/act_b>"
_ACT_C = "action<my.domain.com:my_lib:/act_c>"
_SHARED = "action<my.domain.com:my_lib:/shared>"

_SHARED_OCCUPIED_REQ = (
    "define the potential action<my.domain.com:my_lib:/shared> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    define the position<dest>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        move the particle in position<item> to position<dest>.\n"
    "    }\n"
    "}\n"
)

_SHARED_EMPTY_REQ = (
    "define the potential action<my.domain.com:my_lib:/shared> {\n"
    "    define the position<trigger_pos>.\n"
    "    define the position<item>.\n"
    "    it happens when {\n"
    "        the position<trigger_pos> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<item>.\n"
    "    }\n"
    "}\n"
)

_ACT_B_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
    "    }\n"
    "}\n"
)

_ACT_C_TRIGGERS_SHARED = (
    "define the potential action<my.domain.com:my_lib:/act_c> {\n"
    "    define the position<pp>.\n"
    "    define the position<gateway> {\n"
    "        it may only contain particles where {\n"
    "            it has the action</shared>.\n"
    "        }\n"
    "    }\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
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
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
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
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == _ACT_B
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
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].action_name == _ACT_C
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
    OCCUPIED requirement internally, so it does NOT propagate to /test.
    /act_c does NOT fill position<item>, so the OCCUPIED requirement
    propagates through /act_c to /test. The error is on test.dfn because
    /test does not fill position<item> for /act_c's path either.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": (
                "define the potential action<my.domain.com:my_lib:/shared> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "act_b.dfn": (
                "define the potential action<my.domain.com:my_lib:/act_b> {\n"
                "    define the position<pp>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</shared>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pp> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "act_c.dfn": (
                "define the potential action<my.domain.com:my_lib:/act_c> {\n"
                "    define the position<pp>.\n"
                "    define the position<gateway> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</shared>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pp> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<gateway>::action</shared>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
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
    assert all_diags[0].action_name == _ACT_C
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 21
    assert all_diags[0].location.column == 30
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_top_caller_satisfies_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> occupied (first reference is a move-from).

    Neither /act_b nor /act_c fill position<item>, so the OCCUPIED requirement
    propagates through both to /test. /test fills position<item> for both paths
    before triggering, satisfying both propagated requirements.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_OCCUPIED_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_one_path_violates_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> occupied.

    /test fills position<item> for /act_b's path but not for /act_c's path.
    One ActionRequiresOccupiedPositionDiagnostic for the /act_c path at /test.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_OCCUPIED_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
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
    assert all_diags[0].action_name == _ACT_C
    assert (
        all_diags[0].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.line == 22
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)


def test_diamond_neither_path_satisfies_occupied_requirement(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/shared requires position<item> occupied.

    Neither /act_b nor /act_c fill position<item>, and /test doesn't fill it
    for either path. Two ActionRequiresOccupiedPositionDiagnostics at /test.
    """
    result = validate_project_with_reference_graph(
        {
            "shared.dfn": _SHARED_OCCUPIED_REQ,
            "act_b.dfn": _ACT_B_TRIGGERS_SHARED,
            "act_c.dfn": _ACT_C_TRIGGERS_SHARED,
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<box_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<box_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</act_c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<box_b>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<gateway>.\n"
                "        create a particle in position<box_b>::action</act_b>::position<pp>.\n"
                "        create a particle in position<box_c>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<gateway>.\n"
                "        create a particle in position<box_c>::action</act_c>::position<pp>.\n"
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
    assert all_diags[0].action_name == _ACT_B
    assert (
        all_diags[0].position_name
        == "position<box_b>::action</act_b>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[0],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_B,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_b.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert isinstance(
        all_diags[1], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].action_name == _ACT_C
    assert (
        all_diags[1].position_name
        == "position<box_c>::action</act_c>::position<gateway>::action</shared>::position<item>"
    )
    assert all_diags[1].location.line == 21
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert_propagation_chain(
        all_diags[1],
        {
            "kind": action_contract.PropagationKind.ACTION_TRIGGER,
            "enclosing_quality_name": _ACT_C,
            "triggered_quality_name": _SHARED,
            "line": 11,
            "column": 30,
            "file_path": "act_c.dfn",
        },
        {
            "kind": action_contract.PropagationKind.DIRECT_INFERENCE,
            "enclosing_quality_name": _SHARED,
            "triggered_quality_name": None,
            "line": 8,
            "column": 30,
            "file_path": "shared.dfn",
        },
    )
    assert_action_calls(result.action_call_graph, _TEST, _ACT_B, _SHARED)
    assert_action_calls(result.action_call_graph, _TEST, _ACT_C, _SHARED)
