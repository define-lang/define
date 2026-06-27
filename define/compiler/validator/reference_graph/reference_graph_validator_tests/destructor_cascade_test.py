# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph
from define.compiler.validator.test_helpers import assert_no_errors

_TEST = "action<my.domain.com:my_lib:/test>"
_DESTRUCTOR = "action<my.domain.com:my_lib:/destructor>"
_DESTRUCTOR_A = "action<my.domain.com:my_lib:/destructor_a>"
_DESTRUCTOR_B = "action<my.domain.com:my_lib:/destructor_b>"
_DESTRUCTOR_C = "action<my.domain.com:my_lib:/destructor_c>"
_CHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/child_destructor>"
_PARENT_DESTRUCTOR = "action<my.domain.com:my_lib:/parent_destructor>"
_GRANDCHILD_DESTRUCTOR = "action<my.domain.com:my_lib:/grandchild_destructor>"
_A_BRANCH_DESTRUCTOR = "action<my.domain.com:my_lib:/a_branch_destructor>"
_A_LEAF_DESTRUCTOR = "action<my.domain.com:my_lib:/a_leaf_destructor>"
_B_BRANCH_DESTRUCTOR = "action<my.domain.com:my_lib:/b_branch_destructor>"
_B_LEAF_DESTRUCTOR = "action<my.domain.com:my_lib:/b_leaf_destructor>"


def _named_destructor_noop(name: str) -> str:
    return (
        f"define the potential action<my.domain.com:my_lib:/{name}> {{\n"
        "    it happens when {\n"
        "        this particle is being destroyed.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )


def test_destroy_parent_fires_position_quality_child_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _CHILD_DESTRUCTOR)]


def test_destroy_parent_fires_interface_position_child_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "destructor.dfn": _named_destructor_noop("destructor"),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<slot> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
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
                "        create a particle in position<box>::action</inner>::position<slot>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [(_TEST, _DESTRUCTOR)]


def test_cascade_destroys_interface_positions_in_reverse_definition_order(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Interface positions are destroyed last-defined-first, so the destructors fire slot_c, slot_b, slot_a."""
    result = validate_project_with_reference_graph(
        {
            "destructor_a.dfn": _named_destructor_noop("destructor_a"),
            "destructor_b.dfn": _named_destructor_noop("destructor_b"),
            "destructor_c.dfn": _named_destructor_noop("destructor_c"),
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<slot_a> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor_a>.\n"
                "        }\n"
                "    }\n"
                "    define the position<slot_b> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor_b>.\n"
                "        }\n"
                "    }\n"
                "    define the position<slot_c> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</destructor_c>.\n"
                "        }\n"
                "    }\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
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
                "        create a particle in position<box>::action</inner>::position<slot_a>.\n"
                "        create a particle in position<box>::action</inner>::position<slot_b>.\n"
                "        create a particle in position<box>::action</inner>::position<slot_c>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _DESTRUCTOR_C),
        (_TEST, _DESTRUCTOR_B),
        (_TEST, _DESTRUCTOR_A),
    ]


def test_cascade_fires_grandchild_destructor_before_child(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroying the parent fires the grandchild's destructor before the child's."""
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "grandchild_destructor.dfn": _named_destructor_noop(
                "grandchild_destructor"
            ),
            "grandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</grandchild_destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
                "        it has the position</grandchild>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        create a particle in position<box>::position</child>::position</grandchild>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _GRANDCHILD_DESTRUCTOR),
        (_TEST, _CHILD_DESTRUCTOR),
    ]


def test_cascade_completes_each_subtree_before_the_next_sibling(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """Destroying the parent finishes branch b's whole subtree (leaf then branch) before touching branch a, which a breadth-first walk would not do."""
    result = validate_project_with_reference_graph(
        {
            "a_branch_destructor.dfn": _named_destructor_noop("a_branch_destructor"),
            "a_leaf_destructor.dfn": _named_destructor_noop("a_leaf_destructor"),
            "b_branch_destructor.dfn": _named_destructor_noop("b_branch_destructor"),
            "b_leaf_destructor.dfn": _named_destructor_noop("b_leaf_destructor"),
            "a_leaf.dfn": (
                "define the potential position<my.domain.com:my_lib:/a_leaf> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</a_leaf_destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "a_branch.dfn": (
                "define the potential position<my.domain.com:my_lib:/a_branch> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</a_branch_destructor>.\n"
                "        it has the position</a_leaf>.\n"
                "    }\n"
                "}\n"
            ),
            "b_leaf.dfn": (
                "define the potential position<my.domain.com:my_lib:/b_leaf> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</b_leaf_destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "b_branch.dfn": (
                "define the potential position<my.domain.com:my_lib:/b_branch> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</b_branch_destructor>.\n"
                "        it has the position</b_leaf>.\n"
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
                "                it has the position</a_branch>.\n"
                "                it has the position</b_branch>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</a_branch>.\n"
                "        create a particle in position<box>::position</a_branch>::position</a_leaf>.\n"
                "        create a particle in position<box>::position</b_branch>.\n"
                "        create a particle in position<box>::position</b_branch>::position</b_leaf>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _B_LEAF_DESTRUCTOR),
        (_TEST, _B_BRANCH_DESTRUCTOR),
        (_TEST, _A_LEAF_DESTRUCTOR),
        (_TEST, _A_BRANCH_DESTRUCTOR),
    ]


def test_cascade_fires_child_destructor_before_parents_own(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """A position-quality child's destructor fires before the parent's own destructor."""
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "parent_destructor.dfn": _named_destructor_noop("parent_destructor"),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
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
                "                it has the action</parent_destructor>.\n"
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == [
        (_TEST, _CHILD_DESTRUCTOR),
        (_TEST, _PARENT_DESTRUCTOR),
    ]


def test_cascade_skips_error_position_own_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An error that marks a position's state error stops the cascade from firing its own destructor."""
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "noop.dfn": "define the potential position<my.domain.com:my_lib:/noop>.\n",
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
                "        it has the position</noop>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        move the particle in position<box>::position</child> to position<box>::position</child>::position</noop>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 98
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<box>::position</child>"
    assert (
        all_diags[0].target_position
        == "position<box>::position</child>::position</noop>"
    )
    assert result.action_call_graph.edges() == []


def test_cascade_does_not_walk_subtree_of_error_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    """An error that marks an intermediate position error stops the cascade from firing a descendant's destructor."""
    result = validate_project_with_reference_graph(
        {
            "grandchild_destructor.dfn": _named_destructor_noop(
                "grandchild_destructor"
            ),
            "grandchild.dfn": (
                "define the potential position<my.domain.com:my_lib:/grandchild> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</grandchild_destructor>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the position</grandchild>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<box>::position</child>.\n"
                "        create a particle in position<box>::position</child>::position</grandchild>.\n"
                "        move the particle in position<box>::position</child> to position<box>::position</child>::position</grandchild>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 98
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<box>::position</child>"
    assert (
        all_diags[0].target_position
        == "position<box>::position</child>::position</grandchild>"
    )
    assert result.action_call_graph.edges() == []


def test_destroy_parent_does_not_fire_empty_child_destructor(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_destructor.dfn": _named_destructor_noop("child_destructor"),
            "child.dfn": (
                "define the potential position<my.domain.com:my_lib:/child> {\n"
                "    it may only contain particles where {\n"
                "        it has the action</child_destructor>.\n"
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
                "                it has the position</child>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<box>.\n"
                "        destroy the particle in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    assert_no_errors(result.program_result)
    assert result.action_call_graph.edges() == []
