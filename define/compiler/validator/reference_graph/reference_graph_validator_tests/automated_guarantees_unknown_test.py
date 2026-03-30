# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph


def test_unknown_interface_position_stays_unknown_after_trigger(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<src>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<src>.\n"
                "        move the dimension point in position<src> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<src> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.def")
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 37
    assert all_diags[0].position_name == "position<src>"
    assert isinstance(all_diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.def")
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 54
    assert all_diags[1].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[1].occupied_at is not None
    assert all_diags[1].occupied_at.line == 14
    assert all_diags[1].occupied_at.column == 54


def test_post_trigger_unknown_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37


def test_post_trigger_unknown_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37


def test_post_trigger_unknown_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        move the dimension point in position<item> to position<sink>.\n"
                "        move the dimension point in position<item> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37


def test_post_trigger_unknown_chain_guarantee_suppresses_create_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37


def test_post_trigger_unknown_chain_guarantee_suppresses_move_from_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<box>::action</other>::position<trigger_pos>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37


def test_post_trigger_unknown_chain_guarantee_suppresses_move_to_diagnostic(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.def": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</x>.\n"
                "        }\n"
                "    }\n"
                "    define the position<sink>.\n"
                "    define the position<sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<trigger_pos>::position</x>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink>.\n"
                "        move the dimension point in position<trigger_pos>::position</x> to position<sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<trigger_pos>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37


def test_unknown_from_move_to_occupied_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        define the position<extra>.\n"
                "        create a dimension point in position<extra>.\n"
                "        move the dimension point in position<extra> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 56


def test_unknown_from_constraint_violation_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "quality_a.def": "define the potential position<my.domain.com:my_lib:/quality_a>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</quality_a>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<unconstrained>.\n"
                "        create a dimension point in position<unconstrained>.\n"
                "        move the dimension point in position<unconstrained> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 64


def test_unknown_propagation_from_local_to_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<local>.\n"
                "        define the position<sink>.\n"
                "        create a dimension point in position<local>.\n"
                "        move the dimension point in position<local> to position<sink>.\n"
                "        move the dimension point in position<local> to position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37


@pytest.mark.xfail(
    reason=(
        "apply_guarantees crashes when parent trie nodes for chained "
        "guarantee keys don't exist in the caller's tracker."
    ),
    raises=KeyError,
)
def test_unknown_from_prefix_move_on_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "inner.def": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    define the position<tp>.\n"
                "    it happens when {\n"
                "        the position<tp> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a dimension point in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "mid.def": (
                "define the potential position<my.domain.com:my_lib:/mid> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the action</inner>.\n"
                "    }\n"
                "}\n"
            ),
            "outer.def": (
                "define the potential action<my.domain.com:my_lib:/outer> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<iface> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</mid>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<iface>.\n"
                "        move the dimension point in position<iface> to position<iface>::position</mid>::action</inner>::position<tp>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
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
                "        create a dimension point in position<box>::action</outer>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</outer>::position<iface>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveIntoDefiningPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("outer.def")
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 73


def test_unknown_global_chain_start_treats_action_guarantees_as_unknown(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in action</other>::position<trigger_pos>.\n"
                "        create a dimension point in action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.def")
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert isinstance(all_diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[1].location.file_path == PurePosixPath("test.def")
    assert all_diags[1].source_global_name == "action</other>"
    assert all_diags[1].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[1].location.line == 7


def test_post_trigger_unknown_guarantee_on_child_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_q.def": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink>.\n"
                "        move the dimension point in position<item>::position</child_q> to position<_sink2>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare2>.\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        create a dimension point in position<spare2>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        move the dimension point in position<spare2> to position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37


@pytest.mark.xfail(
    reason=(
        "Unknown state does not propagate to descendants. Children of an "
        "unknown position should also be treated as unknown."
    ),
    raises=KeyError,
)
def test_post_trigger_existing_guarantee_unknown_origin_with_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_q.def": "define the potential position<my.domain.com:my_lib:/child_q>.\n",
            "other.def": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<dest> {\n"
                "        it may only contain dimension points where {\n"
                "            it has the position</child_q>.\n"
                "        }\n"
                "    }\n"
                "    define the position<_sink>.\n"
                "    define the position<_sink2>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position<_sink>.\n"
                "        move the dimension point in position<item> to position<_sink2>.\n"
                "        move the dimension point in position<item> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
            "test.def": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<box> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</child_q>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "        create a dimension point in position<spare>.\n"
                "        move the dimension point in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a dimension point in position<box>::action</other>::position<item>::position</child_q>.\n"
                "        create a dimension point in position<box>::action</other>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</other>::position<dest>::position</child_q>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("other.def")
    assert all_diags[0].location.line == 19
    assert all_diags[0].location.column == 37
