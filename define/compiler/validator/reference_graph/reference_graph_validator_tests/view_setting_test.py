"""Reference graph validation of View Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors
from source_rendering.python import rendering

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
    )


def test_interface_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingInterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=36, column=26, end_line=36, end_column=36
            ),
            view_name="view<value>",
            first_write=rendering.SourceLocation(
                line=35, column=26, end_line=35, end_column=36
            ),
        ),
    ]


def test_local_view_written_twice(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=26, end_line=40, end_column=35
            ),
            view_name="view<copy>",
            first_write=rendering.SourceLocation(
                line=39, column=26, end_line=39, end_column=35
            ),
        ),
    ]


def test_output_only_target(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingOutputOnlyTargetDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=26, end_line=40, end_column=38
            ),
            view_name="view<negated>",
        ),
    ]


def test_read_from_unwritten_local_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=38, column=42, end_line=38, end_column=56
            ),
            view_name="view<unwritten>",
        ),
        diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=37, end_line=40, end_column=51
            ),
            looked_at_name="view<unwritten>",
            view_name="view<a>",
            operation_name="logical_operation</add>",
        ),
    ]


def test_read_from_unwritten_output_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromUnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=30, column=42, end_line=30, end_column=53
            ),
            view_name="view<result>",
        ),
    ]


def test_read_from_written_read_write_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=65, column=42, end_line=65, end_column=52
            ),
            view_name="view<value>",
            write=rendering.SourceLocation(
                line=63, column=42, end_line=63, end_column=52
            ),
        ),
        diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=68, column=37, end_line=68, end_column=47
            ),
            looked_at_name="view<value>",
            view_name="view<b>",
            operation_name="logical_operation</add>",
            write=rendering.SourceLocation(
                line=63, column=42, end_line=63, end_column=52
            ),
        ),
    ]


def test_read_write_target_after_missing_logical_operation(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.NoProjectRootForDefinitionNotInSuppliedSourceDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=21, end_line=31, end_column=47
            ),
            definition_name="logical_operation</missing>",
            config_path=".define/project/config.defcl",
        ),
    ]


def test_read_write_target_after_undefined_executed_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=21, end_line=31, end_column=46
            ),
            view_name="view<result>",
            operation_name="logical_operation</negate>",
        ),
        diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=33, column=18, end_line=33, end_column=32
            ),
            view_name="view<undefined>",
            operation_name="logical_operation</negate>",
            interface_view_names=["view<value>", "view<result>"],
        ),
    ]


def test_read_write_target_not_read(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetNotFromExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=66, column=26, end_line=66, end_column=36
            ),
            target_name="view<value>",
            source_name="view<negated>",
        ),
    ]


def test_read_write_target_source_not_local(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetSourceNotLocalDiagnostic(
            location=rendering.SourceLocation(
                line=42, column=43, end_line=42, end_column=54
            ),
            target_name="view<value>",
            source_name="view<number>",
        ),
    ]


def test_read_write_target_source_not_written(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetNotFromExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=72, column=26, end_line=72, end_column=36
            ),
            target_name="view<value>",
            source_name="view<negated>",
        ),
    ]


def test_read_write_target_without_execution(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=46, column=26, end_line=46, end_column=36
            ),
            target_name="view<value>",
        ),
    ]


def test_same_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.ViewSettingSameViewDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=45, end_line=40, end_column=57
            ),
            view_name="view<negated>",
        ),
    ]


def test_undefined_source(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=39, column=42, end_line=39, end_column=54
            ),
            local_name="view<missing>",
        ),
    ]


def test_undefined_target(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=40, column=26, end_line=40, end_column=38
            ),
            local_name="view<missing>",
        ),
    ]


def test_valid_view_setting(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)
