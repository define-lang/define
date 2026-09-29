"""Reference graph validation of Dead Value Writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_overwritten_value_is_dead(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueWriteDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 13
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position</number>"


def test_unused_value_is_dead(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueWriteDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 12
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<number>"


def test_unused_operation_output_is_dead(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueWriteDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 39
    assert diagnostic.location.column == 42
    assert diagnostic.position_name == "position<second>"


def test_value_read_by_value_setting_is_used(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    assert_no_errors(validate_testdata_non_filesystem_with_reference_graph())


def test_value_read_by_input_view_is_used(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    assert_no_errors(validate_testdata_non_filesystem_with_reference_graph())


def test_value_required_by_callee_is_used(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    assert_no_errors(validate_testdata_non_filesystem_with_reference_graph())


def test_value_guaranteed_through_interface_position_is_used(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    assert_no_errors(validate_testdata_non_filesystem_with_reference_graph())


def test_value_required_by_destructor_is_used(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    assert_no_errors(validate_testdata_non_filesystem_with_reference_graph())


def test_value_on_destroyed_caller_particle_is_dead(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueWriteDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 17
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<input>::position</value>"


def test_copied_value_error_is_not_a_dead_write(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.UnsetValueDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 24
    assert diagnostic.location.column == 45
    assert diagnostic.position_name == "position<source>"


def test_callee_written_value_on_destroyed_particle_is_not_tracked_by_caller(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.DeadValueWriteDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 56
    assert diagnostic.location.column == 26
    assert diagnostic.position_name == "position<input>::position</value>"
