# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph

_PARENT = "my.domain.com:parent_lib"
_CHILD = "my.domain.com:child_lib"


def test_move_interface_to_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<item> to position</implied>.\n"
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
                "        create a dimension point in position<box>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
                "        destroy the dimension point in position<box>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 85
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 51
    assert all_diags[0].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 70
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].created_at.line == 8
    assert all_diags[1].created_at.column == 55
    assert all_diags[1].created_at.end_line == 8
    assert all_diags[1].created_at.end_column == 73
    assert all_diags[1].created_at.file_path == PurePosixPath("inner.dfn")


def test_move_implied_to_interface(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position</implied>.\n"
                "        move the dimension point in position</implied> to position<item>.\n"
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
                "        create a dimension point in position<box>::action</inner>::position<item>.\n"
                "        destroy the dimension point in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].created_at.line == 9
    assert all_diags[0].created_at.column == 59
    assert all_diags[0].created_at.end_line == 9
    assert all_diags[0].created_at.end_column == 73
    assert all_diags[0].created_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 40
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 73
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"


def test_move_interface_through_implied_back_to_interface(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<src>.\n"
                "    define the position<dest>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        move the dimension point in position<src> to position</implied>.\n"
                "        move the dimension point in position</implied> to position<dest>.\n"
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
                "        create a dimension point in position<box>::action</inner>::position<src>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</inner>::position<dest>.\n"
                "        destroy the dimension point in position<box>::action</inner>::position<src>.\n"
                "        destroy the dimension point in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<dest>"
    assert all_diags[0].created_at.line == 10
    assert all_diags[0].created_at.column == 59
    assert all_diags[0].created_at.end_line == 10
    assert all_diags[0].created_at.end_column == 73
    assert all_diags[0].created_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(
        all_diags[1], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 40
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 84
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::action</inner>::position<src>"
    assert all_diags[1].inferred_at is not None
    assert all_diags[1].inferred_at.line == 9
    assert all_diags[1].inferred_at.column == 37
    assert all_diags[1].inferred_at.end_line == 9
    assert all_diags[1].inferred_at.end_column == 50
    assert all_diags[1].inferred_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[2], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert all_diags[2].location.line == 16
    assert all_diags[2].location.column == 40
    assert all_diags[2].location.end_line == 16
    assert all_diags[2].location.end_column == 73
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].position_name == "position<box>::position</implied>"


def test_interface_to_implied_propagates_across_fqun(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "lib/implied.dfn": f"define the potential position<{_CHILD}:/implied>.\n",
            "lib/inner.dfn": (
                f"define the potential action<{_CHILD}:/inner> {{\n"
                f"    it also assigns the position</implied>.\n"
                f"    define the position<trigger_pos>.\n"
                f"    define the position<item>.\n"
                f"    it happens when {{\n"
                f"        the position<trigger_pos> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        move the dimension point in position<item> to position</implied>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.dfn": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<box> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the action<{_CHILD}:/inner>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<box>.\n"
                f"        create a dimension point in position<box>::action<{_CHILD}:/inner>::position<item>.\n"
                f"        create a dimension point in position<box>::action<{_CHILD}:/inner>::position<trigger_pos>.\n"
                f"        destroy the dimension point in position<box>::action<{_CHILD}:/inner>::position<item>.\n"
                f"        create a dimension point in position<box>::position<{_CHILD}:/implied>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 40
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 109
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert (
        all_diags[0].position_name
        == f"position<box>::action<{_CHILD}:/inner>::position<item>"
    )
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.end_line == 8
    assert all_diags[0].inferred_at.end_column == 51
    assert all_diags[0].inferred_at.file_path == PurePosixPath("lib/inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 94
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == f"position<box>::position<{_CHILD}:/implied>"
    assert all_diags[1].created_at.line == 8
    assert all_diags[1].created_at.column == 55
    assert all_diags[1].created_at.end_line == 8
    assert all_diags[1].created_at.end_column == 73
    assert all_diags[1].created_at.file_path == PurePosixPath("lib/inner.dfn")


def test_action_creates_in_both_interface_and_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        create a dimension point in position<item>.\n"
                "        create a dimension point in position</implied>.\n"
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
                "        create a dimension point in position<box>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 13
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].created_at.line == 8
    assert all_diags[0].created_at.column == 37
    assert all_diags[0].created_at.end_line == 8
    assert all_diags[0].created_at.end_column == 51
    assert all_diags[0].created_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 14
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 14
    assert all_diags[1].location.end_column == 70
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].created_at.line == 9
    assert all_diags[1].created_at.column == 37
    assert all_diags[1].created_at.end_line == 9
    assert all_diags[1].created_at.end_column == 55
    assert all_diags[1].created_at.file_path == PurePosixPath("inner.dfn")


def test_swap_interface_and_implied_via_local(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "implied.dfn": "define the potential position<my.domain.com:my_lib:/implied>.\n",
            "inner.dfn": (
                "define the potential action<my.domain.com:my_lib:/inner> {\n"
                "    it also assigns the position</implied>.\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<_tmp>.\n"
                "        create a dimension point in position</implied>.\n"
                "        move the dimension point in position<item> to position<_tmp>.\n"
                "        move the dimension point in position</implied> to position<item>.\n"
                "        move the dimension point in position<_tmp> to position</implied>.\n"
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
                "        create a dimension point in position<box>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::action</inner>::position<trigger_pos>.\n"
                "        create a dimension point in position<box>::action</inner>::position<item>.\n"
                "        create a dimension point in position<box>::position</implied>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.end_line == 14
    assert all_diags[0].location.end_column == 82
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</inner>::position<item>"
    assert all_diags[0].created_at.line == 11
    assert all_diags[0].created_at.column == 59
    assert all_diags[0].created_at.end_line == 11
    assert all_diags[0].created_at.end_column == 73
    assert all_diags[0].created_at.file_path == PurePosixPath("inner.dfn")
    assert isinstance(all_diags[1], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[1].location.line == 15
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.end_line == 15
    assert all_diags[1].location.end_column == 70
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<box>::position</implied>"
    assert all_diags[1].created_at.line == 12
    assert all_diags[1].created_at.column == 55
    assert all_diags[1].created_at.end_line == 12
    assert all_diags[1].created_at.end_column == 73
    assert all_diags[1].created_at.file_path == PurePosixPath("inner.dfn")
