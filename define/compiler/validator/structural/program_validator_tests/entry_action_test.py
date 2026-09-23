from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_interface_position_is_rejected(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    assert isinstance(
        result.all_diagnostics[0], diagnostics.EntryPointInterfacePositionDiagnostic
    )
    assert result.all_diagnostics[0].position_name == "position<input>"
    assert result.all_diagnostics[0].location.line == 2
    assert result.all_diagnostics[0].location.column == 16
    assert result.all_diagnostics[0].location.file_path == PurePosixPath("test.dfn")


def test_each_interface_position_is_rejected(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    assert isinstance(
        result.all_diagnostics[0], diagnostics.EntryPointInterfacePositionDiagnostic
    )
    assert result.all_diagnostics[0].position_name == "position<run>"
    assert result.all_diagnostics[0].location.line == 2
    assert result.all_diagnostics[0].location.column == 16
    assert result.all_diagnostics[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(
        result.all_diagnostics[1], diagnostics.EntryPointInterfacePositionDiagnostic
    )
    assert result.all_diagnostics[1].position_name == "position<input>"
    assert result.all_diagnostics[1].location.line == 3
    assert result.all_diagnostics[1].location.column == 16
    assert result.all_diagnostics[1].location.file_path == PurePosixPath("test.dfn")


def test_validation_escape_allows_interface_positions(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(allow_entry_action_interface_positions=True)
    assert_no_errors(result)


def test_referenced_action_may_have_interface_positions(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)


def test_non_filesystem_only_last_constructor_interfaces_are_rejected(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    first, second = result.all_diagnostics
    assert isinstance(first, diagnostics.EntryPointInterfacePositionDiagnostic)
    assert isinstance(second, diagnostics.EntryPointInterfacePositionDiagnostic)
    assert first.position_name == "position<input>"
    assert first.location.line == 12
    assert first.location.column == 16
    assert first.location.file_path is None
    assert second.position_name == "position<other>"
    assert second.location.line == 13
    assert second.location.column == 16
    assert second.location.file_path is None
    assert (
        result.entry_action is result.file_results[0].definition_results[1].definition
    )


def test_non_filesystem_validation_escape_allows_interface_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem(
        allow_entry_action_interface_positions=True
    )
    assert_no_errors(result)


def test_non_filesystem_without_constructor_can_be_validated(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert result.entry_action is None


def test_non_filesystem_referenced_constructor_is_not_the_entry_point(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    assert result.entry_action is None


def test_non_filesystem_entry_with_filesystem_constructor(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)
    entry_action = result.entry_action
    assert entry_action is not None
    assert (
        entry_action.typed_name.full_typed_name == "action<my.domain.com:my_lib:/start>"
    )
    assert entry_action.location.file_path is None
    assert len(result.file_results) == 2
