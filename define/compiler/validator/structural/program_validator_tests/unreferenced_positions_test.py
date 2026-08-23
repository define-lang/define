"""Dead-code detection for interface and local positions never referenced.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_unreferenced_interface_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<unused_iface>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_unreferenced_local_position_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<unused_local>"
    assert diags[0].location.line == 8
    assert diags[0].location.column == 29


def test_two_unreferenced_local_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<first_unused>"
    assert diags[0].location.line == 8
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[1].position_name == "position<second_unused>"
    assert diags[1].location.line == 9
    assert diags[1].location.column == 29


def test_trigger_only_interface_position_is_referenced(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    # TODO: Decide whether this is the right behavior.
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_positions_referenced_by_create_move_destroy_are_alive(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_position_referenced_as_chain_prefix_is_alive(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
