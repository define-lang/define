# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the position init guarantee scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_self_create_guarantee_visible_to_caller(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Position /a creates in itself. Action creates DP requiring /a, then creating in child gives error."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
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
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>::position</a>"


def test_nested_init_block_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. Both create in themselves. Both child positions are occupied after create."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": (
                "define the potential position<my.domain.com:my_lib:/dep> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</dep>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
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
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</a>.\n"
                "        create a dimension point in position<box>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # Both creates should fail because the init blocks already filled them.
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>::position</a>"
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].position_name == "position<box>::position</a>::position</dep>"


def test_init_block_overrides_inner_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. /dep creates in itself. /a moves DP out of /dep to a sink. Caller sees /dep empty."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": (
                "define the potential position<my.domain.com:my_lib:/dep> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</dep>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
                "        define the position<_sink>.\n"
                "        move the dimension point in position</a>::position</dep> to position<_sink>.\n"
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
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # /dep was moved out by /a's init block, so creating there should succeed.
    assert_no_errors(result.program_result)


def test_no_init_block_no_effect(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Quality without init block produces no extra guarantees when assigned."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # position</a> has no init block, so creating in the child succeeds.
    assert_no_errors(result.program_result)


def test_inferred_occupied_does_not_apply_init_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inferred OCCUPIED with init block qualities does NOT apply init block effects."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # position<item> is inferred OCCUPIED (from the move source).
    # Its quality /a has an init block, but the caller may have already
    # emptied position</a>, so we don't assume it's filled.
    # The create succeeds because we infer an EMPTY requirement.
    assert_no_errors(result.program_result)


def test_caller_sees_init_block_child_guarantees_through_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner has interface position<item> requiring /a. /a creates in itself. /outer calls /inner and sees /a's guarantee."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
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
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</inner>::position<item>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # /inner created a DP in position<item>, which assigned quality /a.
    # /a's init block filled position</a>. That guarantee should propagate
    # through /inner's contract to /test. The create should fail.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>"
    )


def test_nested_quality_guarantees_visible_through_action_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. Both create in themselves. /inner creates DP requiring /a. /outer sees full chain."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": (
                "define the potential position<my.domain.com:my_lib:/dep> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</dep>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</a>.\n"
                "        }\n"
                "    }\n"
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
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</inner>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</inner>::position<item>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # /inner created DP in position<item> requiring /a.
    # /a's init block filled position</a>. /a requires /dep.
    # /dep's init block filled position</dep>.
    # So the full chain ...::position</a>::position</dep> is occupied.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>::position</dep>"
    )


_PARENT_FQUN = "mv:define-lang.org:parent"
_CHILD_FQUN = "mv:define-lang.org:child"


def test_cross_universe_constraint_triggers_init_block(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/a.dfn": (
                f"define the potential position<{_CHILD_FQUN}:/a> {{\n"
                f"    after it is assigned {{\n"
                f"        create a dimension point in position</a>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/b.dfn": (
                f"define the potential position<{_CHILD_FQUN}:/b> {{\n"
                f"    it may only contain dimension points where {{\n"
                f"        it has the position</a>.\n"
                f"    }}\n"
                f"    after it is assigned {{\n"
                f"        create a dimension point in position</b>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_PARENT_FQUN}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<box> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD_FQUN}:/b>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<box>.\n"
                f"        create a dimension point in position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>.\n"
                f"        create a dimension point in position<box>::position<{_CHILD_FQUN}:/b>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT_FQUN,
        local_deps={_CHILD_FQUN: "lib"},
        sub_roots={"lib": _CHILD_FQUN},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 128
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>"
    )
    assert all_diags[0].populated_at.line == 3
    assert all_diags[0].populated_at.column == 37
    assert all_diags[0].populated_at.end_line == 3
    assert all_diags[0].populated_at.end_column == 49
    assert all_diags[0].populated_at.file_path == PurePosixPath("lib/a.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 13
    assert all_diags[1].location.end_column == 89
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == f"position<box>::position<{_CHILD_FQUN}:/b>"
    assert all_diags[1].populated_at.line == 6
    assert all_diags[1].populated_at.column == 37
    assert all_diags[1].populated_at.end_line == 6
    assert all_diags[1].populated_at.end_column == 49
    assert all_diags[1].populated_at.file_path == PurePosixPath("lib/b.dfn")


def test_init_block_applies_after_non_position_quality_in_constraints(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Init block applies even when an action quality precedes its position in constraints.

    /target has constraints [action</foo>, position</bar>] in source order.
    /bar has an init block creating in itself. When the caller creates a DP at
    position</target>, /bar's init block must run for position</bar> even
    though an action quality precedes it in the constraint list.
    """
    result = validate_project_with_reference_graph(
        {
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<_iface>.\n"
                "    it happens when {\n"
                "        the position<_iface> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": (
                "define the potential position<my.domain.com:my_lib:/bar> {\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</bar>.\n"
                "    }\n"
                "}\n"
            ),
            "target.dfn": (
                "define the potential position<my.domain.com:my_lib:/target> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</foo>.\n"
                "        it has the position</bar>.\n"
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
                "                it has the position</target>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::position</target>.\n"
                "        create a dimension point in position<box>::position</target>::position</bar>.\n"
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
    assert all_diags[0].location.end_column == 85
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "position<box>::position</target>::position</bar>"
    )
    assert all_diags[0].populated_at.line == 3
    assert all_diags[0].populated_at.column == 37
    assert all_diags[0].populated_at.end_line == 3
    assert all_diags[0].populated_at.end_column == 51
    assert all_diags[0].populated_at.file_path == PurePosixPath("bar.dfn")
