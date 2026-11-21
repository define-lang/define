"""Reference graph validation of Matching View Requirements for Operation Argument Statements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from define.compiler.errors import reference_graph_diagnostics, structural_diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import (
        ValidateTestdataNonFilesystemWithReferenceGraph,
        ValidateTestdataProjectWithReferenceGraph,
    )

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]


def test_extra_caller_quality_assignments(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_duplicate_caller_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(diagnostic, structural_diagnostics.LocalNameConflictDiagnostic)
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 31
    assert diagnostic.location.column == 16
    assert diagnostic.local_name == "number"
    assert diagnostic.first_definition_line == 25


def test_value_mismatch(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=rendering.SourceLocation(
                line=17, column=42, end_line=17, end_column=53, file_path="double.dfn"
            ),
            view_name="view<source>",
            looked_at_name="view<number>",
            looked_at_kind=reference_graph_diagnostics.LookedAtKind.VIEW,
            missing_qualities=["value<standard:/number/natural>"],
        )
    ]


def test_literal_for_view_without_value(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 2
    first = result.sorted_diagnostics()[0]
    assert isinstance(first, structural_diagnostics.ViewMissingValueQualityDiagnostic)
    assert first.location.file_path is None
    assert first.location.line == 3
    assert first.location.column == 16
    assert first.view_name == "view<source>"
    second = result.sorted_diagnostics()[1]
    assert isinstance(
        second, structural_diagnostics.ValueOperationViewEncodingDiagnostic
    )
    assert second.location.file_path is None
    assert second.location.line == 6
    assert second.location.column == 24
    assert second.quality_name == "encoding<standard:/number/decimal/ascii>"


def test_looks_at_undefined_view(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        structural_diagnostics.UndefinedLocalNameDiagnostic(
            location=rendering.SourceLocation(
                line=34, column=42, end_line=34, end_column=54, file_path=None
            ),
            local_name="view<missing>",
        )
    ]


def test_position_missing_value_quality(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=rendering.SourceLocation(
                line=39, column=42, end_line=39, end_column=57, file_path=None
            ),
            view_name="view<target>",
            looked_at_name="position<second>",
            looked_at_kind=reference_graph_diagnostics.LookedAtKind.POSITION,
            missing_qualities=["value<standard:/number/natural>"],
        )
    ]


def test_position_value_mismatch(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph().program_validation
    assert result.sorted_diagnostics() == [
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic(
            location=rendering.SourceLocation(
                line=18, column=42, end_line=18, end_column=57, file_path="run.dfn"
            ),
            view_name="view<target>",
            looked_at_name="position<second>",
            looked_at_kind=reference_graph_diagnostics.LookedAtKind.POSITION,
            missing_qualities=["value<standard:/number/natural>"],
        )
    ]


def test_particle_qualities_in_position_without_assignments(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert_no_errors(result)


def test_comparison_result_value_mismatch(
    validate_testdata_non_filesystem_with_reference_graph: ValidateTestdataNonFilesystemWithReferenceGraph,
):
    result = validate_testdata_non_filesystem_with_reference_graph()
    assert len(result.sorted_diagnostics()) == 1
    diagnostic = result.sorted_diagnostics()[0]
    assert isinstance(
        diagnostic,
        reference_graph_diagnostics.OperationArgumentMissingQualitiesDiagnostic,
    )
    assert diagnostic.location.file_path is None
    assert diagnostic.location.line == 20
    assert diagnostic.location.column == 42
    assert diagnostic.view_name == "view<result>"
    assert diagnostic.looked_at_name == "position<result>"
    assert (
        diagnostic.looked_at_kind == reference_graph_diagnostics.LookedAtKind.POSITION
    )
    assert diagnostic.missing_qualities == ["value<standard:/boolean>"]
