# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import conftest, diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_move_from_empty_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<from_pos>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None


def test_move_to_occupied_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 52
    assert diags[0].position_name == "position<to_pos>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 30
    assert diags[0].occupied_at.line == 9


def test_move_updates_state_allows_create_in_source(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_cannot_create_in_position_that_was_moved_into(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<b>"
    assert diags[0].populated_at.line == 9


def test_double_move_works(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_same_move_twice_in_a_row(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<a>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 10
    assert diags[1].location.column == 45
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 45
    assert diags[1].occupied_at.line == 9


def test_round_trip_move_fails_second_return(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<b>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 11
    assert diags[1].location.column == 45
    assert diags[1].position_name == "position<a>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 45
    assert diags[1].occupied_at.line == 10


def test_two_actions_same_name_one_empty_error_one_clean(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].position_name == "position<from_pos>"
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None


def test_two_actions_same_name_one_occupied_error_one_clean(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 52
    assert all_diags[0].position_name == "position<to_pos>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.line == 9


def test_two_actions_with_move_same_local_names(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_move_from_empty_marks_both_positions_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<a>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None


def test_move_to_occupied_marks_both_positions_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 10
    assert diags[0].location.column == 45
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 30
    assert diags[0].occupied_at.line == 9


def test_both_from_empty_and_to_occupied_marks_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 9
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<a>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 9
    assert diags[1].location.column == 45
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 30
    assert diags[1].occupied_at.line == 8


def test_error_state_does_not_affect_other_positions(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 30
    assert diags[0].position_name == "position<a>"
    assert diags[0].is_action_interface_position is False
    assert diags[0].inferred_at is None
    assert isinstance(diags[1], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[1].location.line == 11
    assert diags[1].location.column == 45
    assert diags[1].position_name == "position<b>"
    assert diags[1].occupied_at is not None
    assert diags[1].occupied_at.column == 45
    assert diags[1].occupied_at.line == 10


def test_single_error_position_marks_both_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert diags[0].location.line == 11
    assert diags[0].location.column == 45
    assert diags[0].position_name == "position<b>"
    assert diags[0].occupied_at is not None
    assert diags[0].occupied_at.column == 30
    assert diags[0].occupied_at.line == 10


def test_move_from_chained_to_occupied_local_position(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 61
    assert all_diags[0].position_name == "position<dest>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.line == 14


def test_move_from_empty_local_chained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 13
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<src>::position</x>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None


def test_move_to_occupied_local_chained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveToOccupiedPositionDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 47
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<dest>::position</x>"
    assert all_diags[0].occupied_at is not None
    assert all_diags[0].occupied_at.line == 14
    assert all_diags[0].occupied_at.column == 30
    assert all_diags[0].occupied_at.file_path == PurePosixPath("test.dfn")


def test_double_move_from_local_chained_fails(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveFromEmptyPositionDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<src>::position</x>"
    assert all_diags[0].is_action_interface_position is False
    assert all_diags[0].inferred_at is None


def test_move_from_local_chained_to_local(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_from_local_to_local_chained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_between_local_chained(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)
