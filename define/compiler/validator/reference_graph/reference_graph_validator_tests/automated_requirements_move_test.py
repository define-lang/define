# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the automated guarantee/requirement scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph


def test_caller_sees_requirement_when_interface_moved_to_local(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/outer moves iface to local and triggers /inner via local.

    The EMPTY requirement on trigger_pos is NOT in /inner's contract (trigger
    positions are excluded), so _propagate_inner_requirements doesn't catch it.
    Only _maybe_infer_requirement with from_caller tracking creates this
    requirement in /outer's contract, remapped through position<iface>.
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
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>.\n"
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
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<trigger_pos>"
    )
    assert all_diags[0].inferred_at.line == 17
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []


def test_caller_sees_requirement_on_unused_position_when_interface_moved_to_local(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/outer moves iface to local and creates in an /inner position that /inner doesn't use.

    position<extra> is not referenced by /inner's body, so /inner's contract has
    no requirement for it and _propagate_inner_requirements doesn't propagate one.
    Only _maybe_infer_requirement with from_caller tracking creates the EMPTY
    requirement in /outer's contract, remapped through position<iface>.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<extra>.\n"
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
                "        create a dimension point in position<local>::action</inner>::position<extra>.\n"
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
                "        create a dimension point in position<box>::action</outer>::position<iface>::action</inner>::position<extra>.\n"
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
    assert all_diags[0].action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        all_diags[0].position_name
        == "position<box>::action</outer>::position<iface>::action</inner>::position<extra>"
    )
    assert all_diags[0].inferred_at.line == 17
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("outer.dfn")
    assert all_diags[0].filled_at.line == 13
    assert all_diags[0].filled_at.column == 37
    assert all_diags[0].filled_at.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].propagated_from_locations == []


def test_requirement_inferred_when_trigger_moved_to_local(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/outer moves its trigger position to a local, then creates in a child via local.

    The trigger position has from_caller=True. Moving it to a local preserves
    that flag, so children of the local should still infer requirements remapped
    through the trigger position.

    The caller pre-fills position<extra> by constructing a DP in a spare position
    and moving it into the trigger position. /inner does not use position<extra>,
    so _propagate_inner_requirements does not propagate a requirement for it --
    only _maybe_infer_requirement with from_caller tracking catches the violation.
    """
    result = validate_project_with_reference_graph(
        {
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<extra>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.dfn": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos> {\n"
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
                "        move the dimension point in position<trigger_pos> to position<local>.\n"
                "        create a dimension point in position<local>::action</inner>::position<extra>.\n"
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
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare>::action</inner>::position<extra>.\n"
                "        move the dimension point in position<spare> to position<box>::action</outer>::position<trigger_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(diag, diagnostics.ActionRequiresEmptyPositionDiagnostic)
    assert diag.action_name == "action<my.domain.com:my_lib:/outer>"
    assert (
        diag.position_name
        == "position<box>::action</outer>::position<trigger_pos>::action</inner>::position<extra>"
    )
    assert diag.inferred_at.line == 16
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("outer.dfn")
    assert diag.filled_at.line == 18
    assert diag.filled_at.column == 37
    assert diag.filled_at.file_path == PurePosixPath("test.dfn")
    assert diag.propagated_from_locations == []
