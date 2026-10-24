# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler import conftest


def test_move_missing_dest_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 52
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_move_from_position_without_qualities_to_position_with_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 52
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position</x>",
    ]


def test_move_with_compatible_quality_assignments(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_local_move_round_trip_with_quality_assignment_subset(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_local_move_missing_qualities_marks_error(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 52
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_move_to_position_without_qualities(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_definition_local_to_statement_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 51
    assert all_diags[0].source_position == "position<def_pos>"
    assert all_diags[0].target_position == "position<stmt_pos>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_definition_local_to_statement_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_statement_local_to_definition_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.line == 16
    assert all_diags[0].location.column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<stmt_pos>"
    assert all_diags[0].target_position == "position<def_pos>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_statement_local_to_definition_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_definition_local_to_definition_local_violates(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveMissingQualitiesDiagnostic)
    assert all_diags[0].location.line == 15
    assert all_diags[0].location.column == 52
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].source_position == "position<from_pos>"
    assert all_diags[0].target_position == "position<to_pos>"
    assert all_diags[0].missing_qualities == [
        "position</y>",
    ]


def test_definition_local_to_definition_local_satisfies(
    validate_testdata_project_with_reference_graph: conftest.ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)
