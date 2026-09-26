from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_local_and_interface_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_same_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingSamePositionDiagnostic)
    assert diagnostic.position_name == "position<item>"
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 7
    assert diagnostic.location.column == 44


def test_same_chained_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 1
    diagnostic = result.all_diagnostics[0]
    assert isinstance(diagnostic, diagnostics.ValueSettingSamePositionDiagnostic)
    assert diagnostic.position_name == "position<item>::position</child>"
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 8
    assert diagnostic.location.column == 62


def test_distinct_parent_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_parent_and_child_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_implied_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_undefined_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    target, source = result.all_diagnostics
    assert isinstance(target, diagnostics.UndefinedLocalNameDiagnostic)
    assert target.local_name == "position<target>"
    assert target.location.file_path is None
    assert target.location.line == 6
    assert target.location.column == 26
    assert isinstance(source, diagnostics.UndefinedLocalNameDiagnostic)
    assert source.local_name == "position<source>"
    assert source.location.file_path is None
    assert source.location.line == 6
    assert source.location.column == 46


def test_invalid_local_chains(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    target, source = result.all_diagnostics
    assert isinstance(target, diagnostics.ChainedLocalNameRequiresActionDiagnostic)
    assert target.preceding_name == "position<target>"
    assert target.local_name == "position<target_child>"
    assert target.location.file_path is None
    assert target.location.line == 8
    assert target.location.column == 44
    assert isinstance(source, diagnostics.ChainedLocalNameRequiresActionDiagnostic)
    assert source.preceding_name == "position<source>"
    assert source.local_name == "position<source_child>"
    assert source.location.file_path is None
    assert source.location.line == 8
    assert source.location.column == 88


def test_unknown_global_positions(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert len(result.all_diagnostics) == 2
    target, source = result.all_diagnostics
    assert isinstance(target, diagnostics.UnknownGlobalNameDiagnostic)
    assert target.full_global_name == "position<my.domain.com:my_lib:/target>"
    assert target.source_global_name == "position</target>"
    assert target.location.file_path is None
    assert target.location.line == 8
    assert target.location.column == 26
    assert isinstance(source, diagnostics.UnknownGlobalNameDiagnostic)
    assert source.full_global_name == "position<my.domain.com:my_lib:/source>"
    assert source.source_global_name == "position</source>"
    assert source.location.file_path is None
    assert source.location.line == 8
    assert source.location.column == 47


def test_chained_references_load_definitions(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)
    assert len(result.file_results) == 3
