# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateProjectWithReferenceGraph,
    ValidateTestdataProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_move_from_child_of_unoccupied_local_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        move the particle in position<local>::position</x> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<local>::position</x>"
    assert all_diags[0].parent_position_name == "position<local>"


def test_move_to_child_of_unoccupied_local_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 47
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<local>::position</x>"
    assert all_diags[0].parent_position_name == "position<local>"


def test_both_source_and_target_have_unoccupied_parents(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src_local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest_local> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        move the particle in position<src_local>::position</x> to position<dest_local>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].position_name == "position<src_local>::position</x>"
    assert all_diags[0].parent_position_name == "position<src_local>"
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].position_name == "position<dest_local>::position</x>"
    assert all_diags[1].parent_position_name == "position<dest_local>"


def test_move_from_and_to_child_of_occupied_parent_succeeds(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "x.dfn": "define the potential position<my.domain.com:my_lib:/x>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<src> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</x>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<src>.\n"
                "        create a particle in position<src>::position</x>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<src>::position</x> to position<dest>::position</x>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    assert_no_errors(result.program_result)
