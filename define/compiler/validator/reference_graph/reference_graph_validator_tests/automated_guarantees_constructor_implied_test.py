# pyright: reportUnusedCallResult=false
# Exception to CLAUDE.md "no docstrings in tests" rule: these tests have docstrings
# because the constructor guarantee scenarios are complex enough to need
# prose explanations of what each test verifies.

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors


def test_nested_constructor_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. A constructor fills each implied position. Both child positions are occupied after create."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": "define the potential position<my.domain.com:my_lib:/dep>.\n",
            "construct_dep.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_dep> {\n"
                "    it also assigns the position</dep>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</construct_dep>.\n"
                "    }\n"
                "}\n"
            ),
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</a>.\n"
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
                "                it has the action</construct_a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a>.\n"
                "        create a particle in position<box>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # Both creates should fail because the constructors already filled them.
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<box>::position</a>"
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].position_name == "position<box>::position</a>::position</dep>"


def test_constructor_overrides_inner_guarantee(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. /dep's constructor fills /dep. /a's constructor moves that particle out to a sink. Caller sees /dep empty."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": "define the potential position<my.domain.com:my_lib:/dep>.\n",
            "construct_dep.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_dep> {\n"
                "    it also assigns the position</dep>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</construct_dep>.\n"
                "    }\n"
                "}\n"
            ),
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</a>.\n"
                "        define the position<_sink>.\n"
                "        move the particle in position</a>::position</dep> to position<_sink>.\n"
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
                "                it has the action</construct_a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # /dep was moved out by /a's constructor, so creating there should succeed.
    assert_no_errors(result.program_result)


def test_no_constructor_no_effect(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A quality with no constructor produces no extra guarantees when assigned."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</a>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # position</a> has no constructor, so creating in the child succeeds.
    assert_no_errors(result.program_result)


def test_inferred_occupied_does_not_apply_constructor_guarantees(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Inferred OCCUPIED with constructor-bearing qualities does NOT apply constructor effects."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    # position<item> is inferred OCCUPIED (not created here), so /construct_a is
    # never fired for it, which the compiler reports as an untriggered action.
    # Crucially there is no CreateInOccupiedPositionDiagnostic: the constructor
    # guarantee is NOT applied to the inferred-occupied position, so creating in
    # position<item>::position</a> does not conflict with any guarantee.
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UntriggeredActionDiagnostic)
    assert all_diags[0].constraint_name == "action</construct_a>"
    assert all_diags[0].position_name == "position<item>"


def test_caller_sees_constructor_child_guarantees_through_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/inner has interface position<item> requiring /a's constructor. /outer calls /inner and sees /a's guarantee."""
    result = validate_project_with_reference_graph(
        {
            "a.dfn": "define the potential position<my.domain.com:my_lib:/a>.\n",
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
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
                "        create a particle in position<box>::action</inner>::position<item>::position</a>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # /inner created a particle in position<item>, firing /a's constructor,
    # which filled position</a>. That guarantee propagates through /inner's
    # contract to /test. The create should fail.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>"
    )


def test_nested_quality_guarantees_visible_through_action_chain(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """/a requires /dep. Constructors fill each implied position. /inner creates a particle requiring /a. /outer sees the full chain."""
    result = validate_project_with_reference_graph(
        {
            "dep.dfn": "define the potential position<my.domain.com:my_lib:/dep>.\n",
            "construct_dep.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_dep> {\n"
                "    it also assigns the position</dep>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</dep>.\n"
                "    }\n"
                "}\n"
            ),
            "a.dfn": (
                "define the potential position<my.domain.com:my_lib:/a> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</construct_dep>.\n"
                "    }\n"
                "}\n"
            ),
            "construct_a.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_a> {\n"
                "    it also assigns the position</a>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</a>.\n"
                "    }\n"
                "}\n"
            ),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</construct_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position<item>.\n"
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
                "        create a particle in position<box>::action</inner>::position<item>::position</a>::position</dep>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    # /inner created a particle in position<item> requiring /a.
    # /a's constructor filled position</a>. /a requires /dep.
    # /dep's constructor filled position</dep>.
    # So the full chain ...::position</a>::position</dep> is occupied.
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert (
        all_diags[0].position_name
        == "position<box>::action</inner>::position<item>::position</a>::position</dep>"
    )


_PARENT_FQUN = "mv:define-lang.org:parent"
_CHILD_FQUN = "mv:define-lang.org:child"


def test_cross_universe_constraint_triggers_constructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/a.dfn": f"define the potential position<{_CHILD_FQUN}:/a>.\n",
            "lib/construct_a.dfn": (
                f"define the potential action<{_CHILD_FQUN}:/construct_a> {{\n"
                f"    it also assigns the position</a>.\n"
                f"    it happens when {{\n"
                f"        this particle is created.\n"
                f"    }} and it does {{\n"
                f"        create a particle in position</a>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/b.dfn": (
                f"define the potential position<{_CHILD_FQUN}:/b> {{\n"
                f"    it may only contain particles where {{\n"
                f"        it has the action</construct_a>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "lib/construct_b.dfn": (
                f"define the potential action<{_CHILD_FQUN}:/construct_b> {{\n"
                f"    it also assigns the position</b>.\n"
                f"    it happens when {{\n"
                f"        this particle is created.\n"
                f"    }} and it does {{\n"
                f"        create a particle in position</b>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_PARENT_FQUN}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a particle.\n"
                f"    }} and it does {{\n"
                f"        define the position<box> {{\n"
                f"            it may only contain particles where {{\n"
                f"                it has the action<{_CHILD_FQUN}:/construct_b>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a particle in position<box>.\n"
                f"        create a particle in position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>.\n"
                f"        create a particle in position<box>::position<{_CHILD_FQUN}:/b>.\n"
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
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 12
    assert all_diags[0].location.end_column == 121
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::position<{_CHILD_FQUN}:/b>::position<{_CHILD_FQUN}:/a>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 42
    assert all_diags[0].populated_at.file_path == PurePosixPath("lib/construct_a.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 13
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.end_line == 13
    assert all_diags[1].location.end_column == 82
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == f"position<box>::position<{_CHILD_FQUN}:/b>"
    assert all_diags[1].populated_at.line == 6
    assert all_diags[1].populated_at.column == 30
    assert all_diags[1].populated_at.end_line == 6
    assert all_diags[1].populated_at.end_column == 42
    assert all_diags[1].populated_at.file_path == PurePosixPath("lib/construct_b.dfn")


def test_constructor_applies_after_non_constructor_action_in_constraints(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A constructor applies even when a non-constructor action quality precedes it in constraints.

    /target has constraints [action</foo>, action</construct_bar>] in source order.
    /construct_bar fills its implied position</bar>. When the caller creates a particle
    at position</target>, /construct_bar must run even though a non-constructor action
    quality precedes it in the constraint list.
    """
    result = validate_project_with_reference_graph(
        {
            "foo.dfn": (
                "define the potential action<my.domain.com:my_lib:/foo> {\n"
                "    define the position<_iface>.\n"
                "    it happens when {\n"
                "        the position<_iface> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "bar.dfn": "define the potential position<my.domain.com:my_lib:/bar>.\n",
            "construct_bar.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_bar> {\n"
                "    it also assigns the position</bar>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</bar>.\n"
                "    }\n"
                "}\n"
            ),
            "target.dfn": (
                "define the potential position<my.domain.com:my_lib:/target> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</foo>.\n"
                "        it has the action</construct_bar>.\n"
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
                "                it has the position</target>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</target>.\n"
                "        create a particle in position<box>::position</target>::position</bar>.\n"
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
    assert all_diags[0].location.end_column == 78
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name == "position<box>::position</target>::position</bar>"
    )
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 44
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct_bar.dfn")


def test_constrained_constructor_assigns_implied_in_parent(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An action assigns /p, /p constrains a constructor, and that constructor assigns the implied /r. The /r guarantee reaches the caller on /p's parent particle, at /p::/r."""
    result = validate_project_with_reference_graph(
        {
            "r.dfn": "define the potential position<my.domain.com:my_lib:/r>.\n",
            "construct_q.dfn": (
                "define the potential action<my.domain.com:my_lib:/construct_q> {\n"
                "    it also assigns the position</r>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        create a particle in position</r>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</construct_q>.\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</p>.\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        create a particle in position</p>.\n"
                "        create a particle in position</p>::position</r>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.end_line == 8
    assert all_diags[0].location.end_column == 56
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</p>::position</r>"
    assert all_diags[0].populated_at.line == 6
    assert all_diags[0].populated_at.column == 30
    assert all_diags[0].populated_at.end_line == 6
    assert all_diags[0].populated_at.end_column == 42
    assert all_diags[0].populated_at.file_path == PurePosixPath("construct_q.dfn")
