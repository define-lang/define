# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_create_in_interface_produces_occupied_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_destroy_in_interface_produces_empty_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<item>"


def test_move_between_interfaces_produces_empty_and_moved_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<source>"
    assert isinstance(
        all_diags[1],
        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic,
    )
    assert all_diags[1].location.line == 7
    assert all_diags[1].location.column == 50
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<dest>"
    assert all_diags[1].origin_name == "position<source>"


def test_destroy_implied_quality_produces_empty_guarantee(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 33
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</marker>"


def test_local_only_destructor_produces_no_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_move_out_and_back_produces_no_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_destructor_triggering_action_that_fills_a_contracted_position_is_forbidden(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 12
    assert all_diags[0].location.column == 79
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</item>"


def test_destructor_triggering_implied_action_that_fills_an_implied_position_is_forbidden(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("updater.dfn")
    assert all_diags[0].position_name == "position</marker>"


def test_create_then_move_out_produces_no_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result.program_result)


def test_destructor_triggering_action_then_destroying_what_it_filled_generates_no_guarantees(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert_no_errors(result.program_result)


def test_destructor_surfaces_nested_guarantee_pending_under_an_interface_position(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 2
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 7
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("b.dfn")
    assert all_diags[0].position_name == "position</out>"
    assert isinstance(
        all_diags[1], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[1].location.line == 10
    assert all_diags[1].location.column == 59
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position</saved>"
