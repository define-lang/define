# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProjectWithReferenceGraph


def test_init_block_occupied_requirement_via_destroy_of_child_of_moved_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q_child>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position</q> to position<local>.\n"
                "        destroy the dimension point in position<local>::position</q_child>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 37
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].create_target_name == "position<box>"
    assert all_diags[0].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert all_diags[0].position_name == "position<box>::position</q>"
    assert all_diags[0].inferred_at.line == 9
    assert all_diags[0].inferred_at.column == 37
    assert all_diags[0].inferred_at.file_path == PurePosixPath("p.dfn")
    assert all_diags[0].propagated_from_locations == []
    assert isinstance(
        all_diags[1], diagnostics.PositionInitBlockRequiresOccupiedPositionDiagnostic
    )
    assert all_diags[1].location.line == 11
    assert all_diags[1].location.column == 37
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].create_target_name == "position<box>"
    assert all_diags[1].init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert (
        all_diags[1].position_name == "position<box>::position</q>::position</q_child>"
    )
    assert all_diags[1].inferred_at.line == 10
    assert all_diags[1].inferred_at.column == 40
    assert all_diags[1].inferred_at.file_path == PurePosixPath("p.dfn")
    assert all_diags[1].propagated_from_locations == []


def test_init_block_empty_requirement_via_create_in_child_of_moved_implied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "q_child.dfn": "define the potential position<my.domain.com:my_lib:/q_child>.\n",
            "q.dfn": (
                "define the potential position<my.domain.com:my_lib:/q> {\n"
                "    it may only contain dimension points where {\n"
                "        it has the position</q_child>.\n"
                "    }\n"
                "    after it is assigned {\n"
                "        create a dimension point in position</q>.\n"
                "        create a dimension point in position</q>::position</q_child>.\n"
                "    }\n"
                "}\n"
            ),
            "p.dfn": (
                "define the potential position<my.domain.com:my_lib:/p> {\n"
                "    it also assigns the position</q>.\n"
                "    after it is assigned {\n"
                "        define the position<local> {\n"
                "            it may only contain dimension points where {\n"
                "                it has the position</q_child>.\n"
                "            }\n"
                "        }\n"
                "        move the dimension point in position</q> to position<local>.\n"
                "        create a dimension point in position<local>::position</q_child>.\n"
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
                "                it has the position</p>.\n"
                "            }\n"
                "        }\n"
                "        create a dimension point in position<box>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    diag = all_diags[0]
    assert isinstance(
        diag, diagnostics.PositionInitBlockRequiresEmptyPositionDiagnostic
    )
    assert diag.location.line == 11
    assert diag.location.column == 37
    assert diag.location.file_path == PurePosixPath("test.dfn")
    assert diag.create_target_name == "position<box>"
    assert diag.init_block_position_name == "position<my.domain.com:my_lib:/p>"
    assert diag.position_name == "position<box>::position</q>::position</q_child>"
    assert diag.inferred_at.line == 10
    assert diag.inferred_at.column == 37
    assert diag.inferred_at.file_path == PurePosixPath("p.dfn")
    assert diag.propagated_from_locations == []
    assert diag.filled_at.line == 7
    assert diag.filled_at.column == 37
    assert diag.filled_at.file_path == PurePosixPath("q.dfn")
