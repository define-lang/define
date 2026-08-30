from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructural


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
