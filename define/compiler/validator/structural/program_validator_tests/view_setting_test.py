"""Structural validation of View Setting Statements.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem


def test_consecutive_local_targets_at_end_of_block(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=39, column=26, end_line=39, end_column=41
            ),
            target_name="view<first_copy>",
        ),
        diagnostics.ViewSettingLocalTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=26, end_line=40, end_column=42
            ),
            target_name="view<second_copy>",
        ),
    ]


def test_input_only_target(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingInputOnlyTargetDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=26, end_line=34, end_column=37
            ),
            view_name="view<number>",
        ),
    ]


def test_local_target_at_end_of_block(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=26, end_line=34, end_column=35
            ),
            target_name="view<copy>",
        ),
    ]


def test_local_target_before_local_view_definition(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=27, column=26, end_line=27, end_column=35
            ),
            target_name="view<copy>",
        ),
    ]


def test_local_target_before_operation_execution_with_literal(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_local_target_before_view_setting_and_other_execution(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalTargetNotLookedAtDiagnostic(
            location=rendering.SourceLocation(
                line=44, column=26, end_line=44, end_column=35
            ),
            target_name="view<copy>",
            source_name="view<number>",
        ),
    ]


def test_local_target_not_looked_at_with_source(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalTargetNotLookedAtDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=26, end_line=30, end_column=35
            ),
            target_name="view<copy>",
            source_name="view<number>",
        ),
    ]


def test_only_view_setting(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.OperationWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=11, column=5, end_line=18, end_column=5
            ),
        ),
    ]


def test_output_only_target(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingOutputOnlyTargetDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=26, end_line=34, end_column=38
            ),
            view_name="view<negated>",
        ),
    ]


def test_read_write_target_source_not_local(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetSourceNotLocalDiagnostic(
            location=rendering.SourceLocation(
                line=35, column=43, end_line=35, end_column=54
            ),
            target_name="view<value>",
            source_name="view<number>",
        ),
    ]


def test_same_view(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingSameViewDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=42, end_line=30, end_column=51
            ),
            view_name="view<copy>",
        ),
    ]


def test_source_was_target(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingSourceWasTargetDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=49, end_line=42, end_column=64
            ),
            view_name="view<first_copy>",
            target_line=41,
        ),
    ]


def test_target_without_value_quality(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewMissingValueQualityDiagnostic(
            location=rendering.SourceLocation(
                line=11, column=16, end_line=11, end_column=26
            ),
            view_name="view<value>",
        ),
        diagnostics.ValueOperationViewEncodingDiagnostic(
            location=rendering.SourceLocation(
                line=15, column=24, end_line=15, end_column=63
            ),
            quality_name="encoding<standard:/number/decimal/ascii>",
        ),
    ]


def test_undefined_source(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=33, column=42, end_line=33, end_column=54
            ),
            local_name="view<missing>",
        ),
    ]


def test_undefined_target(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=26, end_line=25, end_column=35
            ),
            local_name="view<copy>",
        ),
    ]


def test_valid_view_setting(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_value_quality_mismatch(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingValueQualityMismatchDiagnostic(
            location=rendering.SourceLocation(
                line=33, column=9, end_line=33, end_column=54
            ),
            target_view="view<copy>",
            source_view="view<number>",
            target_value_quality="value<standard:/boolean>",
            source_value_quality="value<standard:/number/integer>",
        ),
    ]
