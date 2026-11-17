"""Reference graph validation of View Setting Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_interface_view_written_twice(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingInterfaceViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=21,
                column=26,
                end_line=21,
                end_column=36,
                file_path="negate_in_place.dfn",
            ),
            view_name="view<value>",
            first_write=rendering.SourceLocation(
                line=20,
                column=26,
                end_line=20,
                end_column=36,
                file_path="negate_in_place.dfn",
            ),
        )
    ]


def test_local_view_written_twice(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingLocalViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=26, end_line=22, end_column=35, file_path="double.dfn"
            ),
            view_name="view<copy>",
            first_write=rendering.SourceLocation(
                line=21, column=26, end_line=21, end_column=35, file_path="double.dfn"
            ),
        )
    ]


def test_output_only_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingOutputOnlyTargetDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=26, end_line=25, end_column=38, file_path="negate.dfn"
            ),
            view_name="view<negated>",
        )
    ]


def test_read_from_unwritten_local_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=20, column=42, end_line=20, end_column=56, file_path="double.dfn"
            ),
            view_name="view<unwritten>",
        ),
        diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=37, end_line=22, end_column=51, file_path="double.dfn"
            ),
            looked_at_name="view<unwritten>",
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/add>",
        ),
    ]


def test_read_from_unwritten_output_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromUnwrittenOutputViewDiagnostic(
            location=rendering.SourceLocation(
                line=15, column=42, end_line=15, end_column=53, file_path="negate.dfn"
            ),
            view_name="view<result>",
        )
    ]


def test_read_from_written_read_write_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=35,
                column=42,
                end_line=35,
                end_column=52,
                file_path="negate_twice_in_place_and_add.dfn",
            ),
            view_name="view<value>",
            write=rendering.SourceLocation(
                line=33,
                column=42,
                end_line=33,
                end_column=52,
                file_path="negate_twice_in_place_and_add.dfn",
            ),
        ),
        diagnostics.ReadFromWrittenReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=38,
                column=37,
                end_line=38,
                end_column=47,
                file_path="negate_twice_in_place_and_add.dfn",
            ),
            looked_at_name="view<value>",
            view_name="view<b>",
            operation_name="logical_operation<standard:/number/add>",
            write=rendering.SourceLocation(
                line=33,
                column=42,
                end_line=33,
                end_column=52,
                file_path="negate_twice_in_place_and_add.dfn",
            ),
        ),
    ]


def test_read_write_target_after_missing_logical_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=16,
                column=39,
                end_line=16,
                end_column=46,
                file_path="negate_in_place.dfn",
            ),
            file_path="missing.dfn",
        )
    ]


def test_read_write_target_after_undefined_executed_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.MissingOperationArgumentDiagnostic(
            location=rendering.SourceLocation(
                line=16,
                column=21,
                end_line=16,
                end_column=62,
                file_path="negate_in_place.dfn",
            ),
            view_name="view<result>",
            operation_name="logical_operation<standard:/number/negate>",
        ),
        diagnostics.UndefinedOperationViewDiagnostic(
            location=rendering.SourceLocation(
                line=18,
                column=18,
                end_line=18,
                end_column=32,
                file_path="negate_in_place.dfn",
            ),
            view_name="view<undefined>",
            operation_name="logical_operation<standard:/number/negate>",
            interface_view_names=["view<a>", "view<result>"],
        ),
    ]


def test_read_write_target_not_read(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetNotFromExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=36,
                column=26,
                end_line=36,
                end_column=36,
                file_path="add_and_negate_in_place.dfn",
            ),
            target_name="view<value>",
            source_name="view<negated>",
        )
    ]


def test_read_write_target_source_not_local(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetSourceNotLocalDiagnostic(
            location=rendering.SourceLocation(
                line=27,
                column=43,
                end_line=27,
                end_column=54,
                file_path="copy_in_place.dfn",
            ),
            target_name="view<value>",
            source_name="view<number>",
        )
    ]


def test_read_write_target_source_not_written(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetNotFromExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=42,
                column=26,
                end_line=42,
                end_column=36,
                file_path="negate_and_add.dfn",
            ),
            target_name="view<value>",
            source_name="view<negated>",
        )
    ]


def test_read_write_target_without_execution(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingReadWriteTargetWithoutExecutionDiagnostic(
            location=rendering.SourceLocation(
                line=31,
                column=26,
                end_line=31,
                end_column=36,
                file_path="negate_in_place.dfn",
            ),
            target_name="view<value>",
        )
    ]


def test_same_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ViewSettingSameViewDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=45, end_line=25, end_column=57, file_path="negate.dfn"
            ),
            view_name="view<negated>",
        )
    ]


def test_undefined_source(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=21, column=42, end_line=21, end_column=54, file_path="double.dfn"
            ),
            local_name="view<missing>",
        )
    ]


def test_undefined_target(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=25, column=26, end_line=25, end_column=38, file_path="negate.dfn"
            ),
            local_name="view<missing>",
        )
    ]


def test_valid_view_setting(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)
