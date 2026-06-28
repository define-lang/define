# pyright: reportUnusedCallResult=false

from pathlib import PurePosixPath

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateNonFilesystemWithReferenceGraph,
    ValidateProjectWithReferenceGraph,
)
from define.compiler.validator.test_helpers import assert_no_errors


def test_destroy_empty_local_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<target>.\n"
        "        destroy the particle in position<target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags[0].location.line == 7
    assert diags[0].location.column == 33
    assert diags[0].position_name == "position<target>"


def test_destroy_already_emptied_interface_position(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "other.dfn": (
                "define the potential action<my.domain.com:my_lib:/other> {\n"
                "    define the position<trigger_pos>.\n"
                "    define the position<item>.\n"
                "    define the position<_sink>.\n"
                "    it happens when {\n"
                "        the position<trigger_pos> has a particle.\n"
                "    } and it does {\n"
                "        move the particle in position<item> to position<_sink>.\n"
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
                "                it has the action</other>.\n"
                "            }\n"
                "        }\n"
                "        define the position<spare>.\n"
                "        create a particle in position<box>.\n"
                "        create a particle in position<spare>.\n"
                "        move the particle in position<spare> to position<box>::action</other>::position<item>.\n"
                "        create a particle in position<box>::action</other>::position<trigger_pos>.\n"
                "        destroy the particle in position<box>::action</other>::position<item>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")


def test_destroy_parent_not_occupied(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_pos.dfn": "define the potential position<my.domain.com:my_lib:/child_pos>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<parent> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_pos>.\n"
                "            }\n"
                "        }\n"
                "        destroy the particle in position<parent>::position</child_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 11
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<parent>::position</child_pos>"
    assert all_diags[0].parent_position_name == "position<parent>"


def test_destroy_prunes_children_within_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_pos.dfn": "define the potential position<my.domain.com:my_lib:/child_pos>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<parent> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_pos>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a particle in position<parent>.\n"
                "        create a particle in position<parent>::position</child_pos>.\n"
                "        destroy the particle in position<parent>.\n"
                "        move the particle in position<parent>::position</child_pos> to position<dest>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<parent>::position</child_pos>"
    assert all_diags[0].parent_position_name == "position<parent>"


def test_destroy_clears_error_state_on_children(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "child_pos.dfn": "define the potential position<my.domain.com:my_lib:/child_pos>.\n",
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<run>.\n"
                "    it happens when {\n"
                "        the position<run> has a particle.\n"
                "    } and it does {\n"
                "        define the position<parent> {\n"
                "            it may only contain particles where {\n"
                "                it has the position</child_pos>.\n"
                "            }\n"
                "        }\n"
                "        define the position<dest>.\n"
                "        create a particle in position<parent>.\n"
                "        create a particle in position<parent>::position</child_pos>.\n"
                "        create a particle in position<dest>.\n"
                "        move the particle in position<parent>::position</child_pos> to position<dest>.\n"
                "        destroy the particle in position<parent>.\n"
                "        create a particle in position<parent>::position</child_pos>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 14
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].location.line == 17
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<parent>::position</child_pos>"
    assert all_diags[1].parent_position_name == "position<parent>"


def test_valid_destroy_local_position(
    validate_non_filesystem_with_reference_graph: ValidateNonFilesystemWithReferenceGraph,
):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<target>.\n"
        "        create a particle in position<target>.\n"
        "        destroy the particle in position<target>.\n"
        "    }\n"
        "}\n"
    )
    result = validate_non_filesystem_with_reference_graph(source)
    assert_no_errors(result)


def test_destroy_chained_name_not_in_constraints(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<x> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</correct>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<x> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<x>::action</wrong>::position<end>.\n"
                "        create a particle in position<x>::action</correct>::position<end>.\n"
                "    }\n"
                "}\n"
            ),
            "correct.dfn": (
                "define the potential action<my.domain.com:my_lib:/correct> {\n"
                "    define the position<end>.\n"
                "    it happens when {\n"
                "        the position<end> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
            "wrong.dfn": (
                "define the potential action<my.domain.com:my_lib:/wrong> {\n"
                "    define the position<end>.\n"
                "    it happens when {\n"
                "        the position<end> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 46
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
    assert all_diags[0].parent_name == "position<x>"


def test_destroy_chained_name_not_in_action(
    validate_project_with_reference_graph: ValidateProjectWithReferenceGraph,
):
    result = validate_project_with_reference_graph(
        {
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    define the position<pos_a> {\n"
                "        it may only contain particles where {\n"
                "            it has the action</child>.\n"
                "        }\n"
                "    }\n"
                "    it happens when {\n"
                "        the position<pos_a> has a particle.\n"
                "    } and it does {\n"
                "        destroy the particle in position<pos_a>::action</child>::position<no_such>.\n"
                "        create a particle in position<pos_a>::action</child>::position<pos_end>.\n"
                "    }\n"
                "}\n"
            ),
            "child.dfn": (
                "define the potential action<my.domain.com:my_lib:/child> {\n"
                "    define the position<pos_end>.\n"
                "    it happens when {\n"
                "        the position<pos_end> has a particle.\n"
                "    } and it does {\n"
                "        define the position<_noop>.\n"
                "        create a particle in position<_noop>.\n"
                "    }\n"
                "}\n"
            ),
        }
    )
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/child>"
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 66
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
