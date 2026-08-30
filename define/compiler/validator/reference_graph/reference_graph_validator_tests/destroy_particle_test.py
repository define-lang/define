# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_destroy_from_chained(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_from_implied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_from_interface(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_from_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_then_create_same_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    assert_no_errors(validate_testdata_project_with_reference_graph().program_result)


def test_destroy_empty_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DestroyInEmptyPositionDiagnostic)
    assert diags[0].location.line == 7
    assert diags[0].location.column == 33
    assert diags[0].position_name == "position<target>"


def test_destroy_already_emptied_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestroyInEmptyInterfacePositionDiagnostic
    )
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<box>::action</other>::position<item>"
    assert all_diags[0].inferred_at is not None
    assert all_diags[0].inferred_at.line == 8
    assert all_diags[0].inferred_at.column == 30
    assert all_diags[0].inferred_at.file_path == PurePosixPath("other.dfn")


def test_destroy_parent_not_occupied(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<parent>::position</child_pos>"
    assert all_diags[0].parent_position_name == "position<parent>"


def test_destroy_prunes_children_within_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<parent>::position</child_pos>"
    assert all_diags[0].parent_position_name == "position<parent>"


def test_destroy_clears_error_state_on_children(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 14
    assert all_diags[0].location.column == 72
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 13
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.ParentPositionNotOccupiedDiagnostic)
    assert all_diags[1].location.line == 16
    assert all_diags[1].location.column == 30
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<parent>::position</child_pos>"
    assert all_diags[1].parent_position_name == "position<parent>"


def test_valid_destroy_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_destroy_chained_name_not_in_constraints(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInConstraintsDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 46
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].element_name == "action<my.domain.com:my_lib:/wrong>"
    assert all_diags[0].parent_name == "position<x>"


def test_destroy_chained_name_not_in_action(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.ChainElementNotInterfacePositionDiagnostic
    )
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == "action<my.domain.com:my_lib:/child>"
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 66
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
