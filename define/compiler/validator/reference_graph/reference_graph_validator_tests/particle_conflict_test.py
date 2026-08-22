# pyright: reportUnusedCallResult=false
"""Particle conflict validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_constructor_duplicate_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<local>"
    assert diags[0].populated_at.line == 6
    assert diags[0].populated_at.column == 30
    assert diags[0].populated_at.end_line == 6
    assert diags[0].populated_at.end_column == 45
    assert diags[0].populated_at.file_path is None
    assert diags[0].location.line == 7
    assert diags[0].location.column == 30
    assert diags[0].location.end_line == 7
    assert diags[0].location.end_column == 45
    assert diags[0].location.file_path is None


def test_duplicate_local_position(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<my_pos>"
    assert diags[0].populated_at.line == 7
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30


def test_different_local_positions(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_undefined_position_not_tracked_for_duplicates(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[0].local_name == "position<no_such_pos>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 30
    assert isinstance(diags[1], diagnostics.UndefinedLocalNameDiagnostic)
    assert diags[1].local_name == "position<no_such_pos>"
    assert diags[1].location.line == 7
    assert diags[1].location.column == 30


def test_two_actions_same_local_position_create_no_error(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_two_actions_same_name_one_duplicate_one_clean(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert all_diags[0].position_name == "position<my_pos>"
    assert all_diags[0].populated_at.line == 7
    assert all_diags[0].location.line == 8
    assert all_diags[0].location.column == 30


def test_three_actions_particle_isolation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_definition_block_position_enforced(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CreateInOccupiedPositionDiagnostic)
    assert diags[0].position_name == "position<outer_pos>"
    assert diags[0].populated_at.line == 7
    assert diags[0].location.line == 8
    assert diags[0].location.column == 30
