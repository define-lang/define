"""Reference graph validation of local views."""

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


def test_valid_logical_operation_execution(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_valid_operation_execution(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert_no_errors(result)


def test_read_before_write(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ReadFromUnwrittenLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=23, column=37, end_line=23, end_column=49, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            view_name="view<a>",
            operation_name="logical_operation<standard:/number/negate>",
        )
    ]


def test_written_twice(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LocalViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=28, column=42, end_line=28, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            view_name="view<result>",
            operation_name="logical_operation<standard:/number/negate>",
            first_write=rendering.SourceLocation(
                line=24, column=42, end_line=24, end_column=54, file_path="test.dfn"
            ),
        )
    ]


def test_unread(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.UnreadLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=20, end_line=17, end_column=32, file_path="test.dfn"
            ),
            view_name="view<negated>",
        )
    ]


def test_write_not_supported(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=24, column=42, end_line=24, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</read_only_number>",
        )
    ]


def test_value_quality_mismatch(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LogicalOperationWriteNotSupportedDiagnostic(
            location=rendering.SourceLocation(
                line=24, column=42, end_line=24, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            logical_operation_name="logical_operation</negate>",
            value_name="value</read_only_number>",
        ),
        diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=rendering.SourceLocation(
                line=27, column=41, end_line=27, end_column=53, file_path="test.dfn"
            ),
            view_name="view<value>",
            looked_at_name="view<negated>",
            looked_at_kind=diagnostics.LookedAtKind.VIEW,
            missing_qualities=["value</number>"],
        ),
    ]


def test_written_by_missing_logical_operation(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=21, end_line=22, end_column=63, file_path="test.dfn"
            ),
            definition_name="logical_operation<standard:/number/missing>",
        )
    ]


def test_duplicate_name(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.LocalNameConflictDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=20, end_line=22, end_column=32, file_path="test.dfn"
            ),
            local_name="negated",
            first_definition_line=17,
        )
    ]


def test_unreferenced(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.UnreferencedLocalViewDiagnostic(
            location=rendering.SourceLocation(
                line=22, column=20, end_line=22, end_column=31, file_path="test.dfn"
            ),
            view_name="view<unused>",
        )
    ]


def test_missing_logical_operation_looks_at_undefined_view(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.StandardDefinitionNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=21, end_line=17, end_column=63, file_path="test.dfn"
            ),
            definition_name="logical_operation<standard:/number/missing>",
        ),
        diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=19, column=42, end_line=19, end_column=56, file_path="test.dfn"
            ),
            local_name="view<undefined>",
        ),
    ]


def test_written_twice_after_unknown_use(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ReferencedFileNotFoundDiagnostic(
            location=rendering.SourceLocation(
                line=26, column=39, end_line=26, end_column=46, file_path="test.dfn"
            ),
            file_path="missing.dfn",
        ),
        diagnostics.LocalViewWrittenTwiceDiagnostic(
            location=rendering.SourceLocation(
                line=31, column=42, end_line=31, end_column=54, file_path="test.dfn"
            ),
            looked_at_name="view<negated>",
            view_name="view<result>",
            operation_name="logical_operation<standard:/number/negate>",
            first_write=rendering.SourceLocation(
                line=24, column=42, end_line=24, end_column=54, file_path="test.dfn"
            ),
        ),
    ]


def test_passed_to_read_write_view_after_write(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=26, column=21, end_line=26, end_column=47, file_path="test.dfn"
            ),
            operation_name="operation</negate_in_place>",
            view_name="view<value>",
        )
    ]


def test_passed_to_read_write_view_before_write(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.all_diagnostics == [
        diagnostics.ExecutedOperationHasReadWriteViewDiagnostic(
            location=rendering.SourceLocation(
                line=16, column=21, end_line=16, end_column=47, file_path="test.dfn"
            ),
            operation_name="operation</negate_in_place>",
            view_name="view<value>",
        )
    ]
