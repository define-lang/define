# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_action_calls, assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_OUTER = "action<my.domain.com:my_lib:/outer>"
_INNER = "action<my.domain.com:my_lib:/inner>"
_MIDDLE = "action<my.domain.com:my_lib:/middle>"


def test_inner_chained_action_empty_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An inner action requires position<item> to be empty (its first reference is a create).

    The test action pre-fills position<box>::action</outer>::position<iface>::action</inner>::position<item>
    before triggering /outer. When /outer triggers /inner internally, /inner's empty requirement
    on position<item> has been propagated into /outer's contract. So the caller gets an error
    because it filled a position that /inner needs empty.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_inner_chained_action_empty_requirement_satisfied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same setup as the propagation test, but the caller does NOT pre-fill position<item>.

    Since /inner requires position<item> to be empty and it IS empty when /outer triggers
    /inner, no error occurs.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_inner_chained_action_occupied_requirement_not_propagated(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """OCCUPIED requirements are NOT propagated — they are the triggering action's responsibility.

    /inner requires position<item> occupied. /outer triggers /inner without filling it.
    The diagnostic is on /outer (it's at fault), not on /test. OCCUPIED requirements
    can't propagate because the caller can't inject state into the callee's tracker.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name == "position<iface>::action</inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_inner_chained_action_occupied_requirement_caller_fill_does_not_help(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """The caller fills position<item> through the chain, but it doesn't help.

    /outer triggers /inner without filling position<item> in its own code.
    Even though /test fills it through the chained name, /outer's tracker is fresh
    and doesn't see the caller's fills. /outer still gets the OCCUPIED violation.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
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
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name == "position<iface>::action</inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_doubly_nested_action_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Three levels of nesting: /test triggers /outer, /outer triggers /middle, /middle triggers /inner.

    /inner requires position<item> to be empty. Each intermediate has a non-trigger
    interface position with the inner action as a constraint. /outer fills
    position<mid_iface> before triggering /middle (satisfying /middle's OCCUPIED
    requirement), which infers EMPTY on position<mid_iface> in /outer's contract.
    The EMPTY requirement on position<item> propagates through /middle and /outer to
    /test. The test pre-fills both position<mid_iface> and position<item>, producing
    two EMPTY violations.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<out_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # /test fills position<mid_iface> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []
    # /test fills position<item> which /inner requires empty (propagated through /middle and /outer)
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert all_diags[1].inferred_at.line == 12
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].filled_at.line == 14
    assert all_diags[1].filled_at.column == 37
    assert all_diags[1].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[1].propagated_from_locations) == 2
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _MIDDLE, _INNER)


def test_doubly_nested_both_outer_and_caller_fill(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same three-level nesting, but both /outer and /test fill position<item>.

    /outer fills position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>
    in its own code, violating /inner's EMPTY requirement directly. The requirement is
    NOT propagated because /outer already inferred a requirement on that key. /test also
    fills the same deeply nested position, but since the requirement isn't propagated,
    /test's fill doesn't produce a propagated diagnostic — only /outer's direct violation
    is reported.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<mid_iface>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<out_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    # /test fills position<mid_iface> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []
    # /test fills position<item> which /outer requires empty (it creates there)
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert all_diags[1].inferred_at.line == 12
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].filled_at.line == 14
    assert all_diags[1].filled_at.column == 37
    assert all_diags[1].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].propagated_from_locations == []
    # /outer fills position<item> which /inner requires empty (propagated through /middle)
    assert isinstance(all_diags[2], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[2].location.line == 13
    assert all_diags[2].location.column == 37
    assert all_diags[2].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[2].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[2].position_name
        == "position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert all_diags[2].inferred_at.line == 11
    assert all_diags[2].inferred_at.column == 37
    assert all_diags[2].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert all_diags[2].filled_at.line == 12
    assert all_diags[2].filled_at.column == 37
    assert all_diags[2].filled_at.file_path == PurePosixPath("outer.dfn")
    assert len(all_diags[2].propagated_from_locations) == 1
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _MIDDLE, _INNER)


def test_four_deep_action_chain_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Four levels of nesting: /a triggers /b, /b triggers /c, /c triggers /d.

    /d requires position<item> to be empty (its first reference is a create). Each
    intermediate action just triggers the next one. The test action pre-fills the deeply
    nested position<item> before triggering /a, and this violation is detected because
    /d's requirement propagates through /c, /b, and /a to the test action.
    """
    result = validate_project_with_reference_graph(
        {
            "d.dfn": (
                "define the potential action<my.domain.com:my_lib:/d> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "c.dfn": (
                "define the potential action<my.domain.com:my_lib:/c> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<c_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</d>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<c_iface>::action</d>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "b.dfn": (
                "define the potential action<my.domain.com:my_lib:/b> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<b_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</c>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<b_iface>::action</c>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential action<my.domain.com:my_lib:/a> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<a_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</b>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<a_iface>::action</b>::position<trigger_pos>.\n"
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
                "                it has the action</a>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</a>::position<a_iface>.\n"
                "        create a dimension point in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>.\n"
                "        create a dimension point in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>.\n"
                "        create a dimension point in position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>.\n"
                "        create a dimension point in position<box>::action</a>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/d>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</a>::position<a_iface>::action</b>::position<b_iface>::action</c>::position<c_iface>::action</d>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("a.dfn")
    assert all_diags[0].filled_at.line == 15
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[0].propagated_from_locations) == 3
    # /a triggers /b without filling position<b_iface>
    assert isinstance(
        all_diags[1], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("a.dfn")
    assert (
        all_diags[1].position_name == "position<a_iface>::action</b>::position<b_iface>"
    )
    assert all_diags[1].inferred_at.line == 11
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("b.dfn")
    assert all_diags[1].propagated_from_locations == []
    # /b triggers /c without filling position<c_iface>
    assert isinstance(
        all_diags[2], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[2].location.line == 11
    assert all_diags[2].location.column == 37
    assert all_diags[2].location.file_path == PurePosixPath("b.dfn")
    assert (
        all_diags[2].position_name == "position<b_iface>::action</c>::position<c_iface>"
    )
    assert all_diags[2].inferred_at.line == 11
    assert all_diags[2].inferred_at.column == 37
    assert all_diags[2].inferred_at.file_path == PurePosixPath("c.dfn")
    assert all_diags[2].propagated_from_locations == []
    assert_action_calls(
        result.action_call_graph,
        _TEST,
        "action<my.domain.com:my_lib:/a>",
        "action<my.domain.com:my_lib:/b>",
        "action<my.domain.com:my_lib:/c>",
        "action<my.domain.com:my_lib:/d>",
    )


def test_only_empty_requirement_propagates_when_inner_has_both(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inner action has two requirements: position<src> OCCUPIED and position<dest> EMPTY.

    /outer triggers /inner without filling position<src>, so /outer gets an OCCUPIED
    violation (not propagated). The EMPTY requirement on position<dest> propagates,
    and /test pre-fills it, so /test gets an EMPTY violation. Two diagnostics total.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<src> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<src>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<dest>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<dest>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 14
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(
        all_diags[1], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("outer.dfn")
    assert (
        all_diags[1].position_name == "position<iface>::action</inner>::position<src>"
    )
    assert all_diags[1].inferred_at.line == 8
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[1].propagated_from_locations == []
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_trigger_position_child_empty_requirement_propagates(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A requirement on a child of the trigger position propagates through the chain.

    /inner has a trigger position constrained with position</x>, and creates in
    position<trigger_pos>::position</x> (EMPTY requirement on that child). /outer
    triggers /inner via its interface position. The EMPTY requirement on the trigger
    position's child propagates to /outer's contract, and /test pre-fills it.
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    # Filling the nested trigger at line 13 fires /inner, which creates in
    # trigger_pos::position</x> via guarantee. Line 14 then tries to create
    # in the same position, which is already occupied.
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    # /test fills position<trigger_pos> which /outer requires empty (it creates there)
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[1].inferred_at.line == 11
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].filled_at.line == 8
    assert all_diags[1].filled_at.column == 13
    assert all_diags[1].filled_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[1].propagated_from_locations == []
    # /test fills position<trigger_pos>::position</x> which /inner requires empty (propagated)
    assert isinstance(all_diags[2], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[2].location.line == 15
    assert all_diags[2].location.column == 37
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[2].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    assert all_diags[2].inferred_at.line == 11
    assert all_diags[2].inferred_at.column == 37
    assert all_diags[2].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[2].filled_at.line == 10
    assert all_diags[2].filled_at.column == 37
    assert all_diags[2].filled_at.file_path == PurePosixPath("inner.dfn")
    assert len(all_diags[2].propagated_from_locations) == 1
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_trigger_position_child_occupied_requirement_does_not_propagate(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<_sink>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        # Here we fail to fill inner's trigger_pos::/x.\n"
                "        create a dimension point in position<iface>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        # Here we fail to fill inner's trigger_pos::/x before calling /outer,"
                "        # but it doesn't matter because we don't propagate OCCUPIED requirements."
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
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
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name
        == "position<iface>::action</inner>::position<trigger_pos>::position</x>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert all_diags[0].propagated_from_locations == []


def test_inner_action_requirement_propagates_after_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Requirement propagates even when the DP is moved to a local position before triggering.

    /outer moves the DP from position<iface> to position<local>, then triggers /inner
    via position<local>::action</inner>::position<trigger_pos>. Since /inner is a
    constraint on position<iface>, its requirements propagate through position<iface>.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<iface> to position<local>.\n"
                "        create a dimension point in position<local>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 17
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


def test_doubly_nested_requirement_propagates_after_move(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Three-level nesting where /middle moves its interface DP before triggering /inner.

    /middle moves the DP from position<mid_iface> to position<local>, then triggers
    /inner through position<local>::action</inner>::position<trigger_pos>. /inner's
    EMPTY requirement on position<item> should propagate through /middle and /outer
    to /test.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position<mid_iface> to position<local>.\n"
                "        create a dimension point in position<local>::action</inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<out_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<out_iface>::action</middle>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<out_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/inner>"
    assert (
        all_diags[1].position_name
        == "position<box>::action</outer>::position<out_iface>::action</middle>::position<mid_iface>::action</inner>::position<item>"
    )
    assert all_diags[1].inferred_at.line == 12
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].filled_at.line == 14
    assert all_diags[1].filled_at.column == 37
    assert all_diags[1].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[1].propagated_from_locations) == 2
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _MIDDLE, _INNER)


def test_no_propagation_when_action_not_triggered_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """No propagation when the action is only triggered on a local position, not the interface.

    /outer has both position<iface> and position<local> constrained with action</inner>.
    It only triggers /inner through position<local>, not through position<iface>.
    Even though action</inner> is a constraint on position<iface>, the requirement
    should NOT propagate through it because /inner was never triggered on that path.
    The test pre-fills position<iface>::action</inner>::position<item> with no error.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::action</inner>::position<trigger_pos>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
    assert_action_calls(result.action_call_graph, _TEST, _OUTER, _INNER)


_MAIN_FQUN = "mv:define-lang.org:main_lib"
_DEP_FQUN = "mv:define-lang.org:dep_lib"


def test_cross_fqun_inner_requirement_renders_correctly(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Cross-FQUN scenario: the inner action and a position it references are in a different FQUN.

    /inner is in _DEP_FQUN, has position<item> constrained with position</x> (also in
    _DEP_FQUN), and creates in position<item>::position</x>. The propagated requirement's
    position_name should use the source form from /outer's code for the action reference
    (fully-qualified) and the source form from /inner's code for position</x>.
    """
    result = validate_project_with_reference_graph(
        {
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_DEP_FQUN}:/inner> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/outer> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                f"            it has the action<{_DEP_FQUN}:/inner>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                f"        create a dimension point in position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a dimension point in position<iface>::action<{_DEP_FQUN}:/inner>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                f"        create a dimension point in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>.\n"
                f"        create a dimension point in position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    # /test fills position<item> which /outer requires empty (it creates there)
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/outer>"
    assert (
        all_diags[0].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []
    # /test fills position<item>::position</x> which /inner requires empty (propagated)
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == f"action<{_DEP_FQUN}:/inner>"
    assert (
        all_diags[1].position_name
        == f"position<box>::action</outer>::position<iface>::action<{_DEP_FQUN}:/inner>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert all_diags[1].inferred_at.line == 12
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[1].filled_at.line == 14
    assert all_diags[1].filled_at.column == 37
    assert all_diags[1].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[1].propagated_from_locations) == 1
    assert_action_calls(
        result.action_call_graph,
        f"action<{_MAIN_FQUN}:/test>",
        f"action<{_MAIN_FQUN}:/outer>",
        f"action<{_DEP_FQUN}:/inner>",
    )


def test_complex_chain_same_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A deeply-chained trigger path through nested actions in the same FQUN.

    /test triggers /foo through position<local>::position</x>::action</foo>::position<trigger_pos>.
    /foo triggers /middle through position<iface>::action</middle>::position<trigger_pos>.
    /middle triggers /bar through position<mid_iface>::action</bar>::position<trigger_pos>.
    /bar requires position<item> to be empty. The propagated position_name should be:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                "define the potential position<my.domain.com:my_lib:/x> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                "define the potential action<my.domain.com:my_lib:/middle> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<mid_iface>::action</bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": (
                "define the potential action<my.domain.com:my_lib:/bar> {\n"
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
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/bar>"
    assert (
        all_diags[0].position_name
        == "position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action</bar>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("foo.dfn")
    assert all_diags[0].filled_at.line == 15
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[0].propagated_from_locations) == 2
    assert isinstance(
        all_diags[1], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("foo.dfn")
    assert all_diags[1].action_name == "action<my.domain.com:my_lib:/middle>"
    assert (
        all_diags[1].position_name
        == "position<iface>::action</middle>::position<mid_iface>"
    )
    assert all_diags[1].inferred_at.line == 11
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert all_diags[1].propagated_from_locations == []
    assert_action_calls(
        result.action_call_graph,
        _TEST,
        "action<my.domain.com:my_lib:/foo>",
        _MIDDLE,
        "action<my.domain.com:my_lib:/bar>",
    )


def test_complex_chain_cross_fqun_position_name(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Same structure as the same-FQUN complex chain, but /bar lives in a different FQUN.

    /bar is in dep_lib and has an interface position with a constraint on position</x>,
    requiring position<item>::position</x> to be empty. /middle fills /bar's
    position<item> to satisfy the occupied requirement. The propagated position_name
    should render /bar and its positions with canonical FQUN names:
    position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<dep_fqun:/bar>::position<item>::position<dep_fqun:/x>
    """
    result = validate_project_with_reference_graph(
        {
            "x.dfn": (
                f"define the potential position<{_MAIN_FQUN}:/x> {{\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</foo>.\n"
                "    }\n"
                "}\n"
            ),
            "lib/x.dfn": f"define the potential position<{_DEP_FQUN}:/x>.\n",
            "lib/bar.dfn": (
                f"define the potential action<{_DEP_FQUN}:/bar> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
            "middle.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/middle> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<mid_iface> {\n"
                "        it may only contain dimension points where {\n"
                f"            it has the action<{_DEP_FQUN}:/bar>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                f"        create a dimension point in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a dimension point in position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "foo.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/foo> {{\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the action</middle>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>::action</middle>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_MAIN_FQUN}:/test> {{\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<local>.\n"
                "        create a dimension point in position<local>::position</x>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>.\n"
                f"        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>.\n"
                f"        create a dimension point in position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>.\n"
                "        create a dimension point in position<local>::position</x>::action</foo>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        },
        universe_name=_MAIN_FQUN,
        local_deps={_DEP_FQUN: "lib"},
        sub_roots={"lib": _DEP_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 17
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].action_name == f"action<{_MAIN_FQUN}:/middle>"
    assert (
        all_diags[0].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>"
    )
    assert all_diags[0].inferred_at.line == 11
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("foo.dfn")
    assert all_diags[0].filled_at.line == 15
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[0].propagated_from_locations) == 1
    assert isinstance(all_diags[1], diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].action_name == f"action<{_DEP_FQUN}:/bar>"
    assert (
        all_diags[1].position_name
        == f"position<local>::position</x>::action</foo>::position<iface>::action</middle>::position<mid_iface>::action<{_DEP_FQUN}:/bar>::position<item>::position<{_DEP_FQUN}:/x>"
    )
    assert all_diags[1].inferred_at.line == 11
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.file_path == PurePosixPath("foo.dfn")
    assert all_diags[1].filled_at.line == 16
    assert all_diags[1].filled_at.column == 37
    assert all_diags[1].filled_at.file_path == PurePosixPath("test.dfn")
    assert len(all_diags[1].propagated_from_locations) == 2
    assert isinstance(
        all_diags[2], diagnostics.ActionRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[2].location.line == 11
    assert all_diags[2].location.column == 37
    assert all_diags[2].location.file_path == PurePosixPath("foo.dfn")
    assert all_diags[2].action_name == f"action<{_MAIN_FQUN}:/middle>"
    assert (
        all_diags[2].position_name
        == "position<iface>::action</middle>::position<mid_iface>"
    )
    assert all_diags[2].inferred_at.line == 11
    assert all_diags[2].inferred_at.column == 37
    assert all_diags[2].inferred_at.file_path == PurePosixPath("middle.dfn")
    assert all_diags[2].propagated_from_locations == []
    assert_action_calls(
        result.action_call_graph,
        f"action<{_MAIN_FQUN}:/test>",
        f"action<{_MAIN_FQUN}:/foo>",
        f"action<{_MAIN_FQUN}:/middle>",
        f"action<{_DEP_FQUN}:/bar>",
    )
