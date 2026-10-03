# pyright: reportUnusedCallResult=false

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
    )


def test_body_error_does_not_add_a_destructor_guarantee_error(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    (diagnostic,) = result.program_result.all_diagnostics
    assert isinstance(diagnostic, diagnostics.MoveFromEmptyPositionDiagnostic)
    assert diagnostic.location.column == 30
    assert diagnostic.is_action_interface_position is False
    assert diagnostic.inferred_at is None
    assert diagnostic.location.file_path == PurePosixPath("test.dfn")
    assert diagnostic.location.line == 11
    assert diagnostic.position_name == "position</item>"


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


def test_destructor_reports_new_particle_it_leaves_but_not_particles_below_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 10
    assert all_diags[0].location.column == 59
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</saved>"


def test_destructor_creating_particle_and_particle_below_it_reports_only_the_upper_particle(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position</saved>"


def test_destructor_triggering_action_whose_callee_fills_an_implied_position_is_forbidden(
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
    assert all_diags[0].location.file_path == PurePosixPath("b.dfn")
    assert all_diags[0].position_name == "position</out>"


def test_destructor_moving_received_particle_back_below_new_particle_does_not_report_it(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph(
        allow_entry_action_interface_positions=True
    )
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(
        all_diags[0], diagnostics.DestructorProducesEmptyGuaranteeDiagnostic
    )
    assert all_diags[0].location.line == 18
    assert all_diags[0].location.column == 30
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[0].position_name == "position<moved>::position</part>"
    assert isinstance(
        all_diags[1],
        diagnostics.DestructorProducesOccupiedByExistingGuaranteeDiagnostic,
    )
    assert all_diags[1].location.line == 19
    assert all_diags[1].location.column == 47
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[1].position_name == "position<moved>"
    assert all_diags[1].origin_name == "position<box>"
    assert isinstance(
        all_diags[2], diagnostics.DestructorProducesOccupiedGuaranteeDiagnostic
    )
    assert all_diags[2].location.line == 20
    assert all_diags[2].location.column == 30
    assert all_diags[2].location.file_path == PurePosixPath("test.dfn")
    assert all_diags[2].position_name == "position<box>"
