# pyright: reportUnusedCallResult=false
"""Quality Implication Statement validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import diagnostics
from define.compiler.data_structures import define_path
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import (
        ValidateTestdataProjectWithReferenceGraph,
        ValidateTestdataStructural,
        ValidateTestdataStructuralNonFilesystem,
    )


def test_non_self_ref_global_in_action_body(
    validate_testdata_project_with_reference_graph: ValidateTestdataProjectWithReferenceGraph,
):
    result = validate_testdata_project_with_reference_graph()
    assert result.program_result.all_exceptions == []
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert all_diags[0].source_global_name == "action</other>"
    assert all_diags[0].full_global_name == "action<my.domain.com:my_lib:/other>"
    assert all_diags[0].location.line == 6
    assert all_diags[0].location.column == 30


def test_two_distinct_used_quality_implication_statements(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_action_implication_used_via_interface_position_chain(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_position_implication_used_only_via_implied_position_chain(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert_no_errors(result)


def test_global_used_without_implication_is_unknown(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[0].source_global_name == "position</foo>"
    assert diags[0].full_global_name == "position<my.domain.com:my_lib:/foo>"
    assert diags[0].location.line == 6
    assert diags[0].location.column == 30


def test_duplicate_implication_in_action_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].first_implication_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25


def test_three_duplicate_implication_two_errors(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    results = result.file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert isinstance(diags[1], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].first_implication_line == 3
    assert diags[0].location.line == 4
    assert diags[0].location.column == 25
    assert diags[1].implication_name == "position</foo>"
    assert diags[1].first_implication_line == 3
    assert diags[1].location.line == 5
    assert diags[1].location.column == 25


def test_duplicate_implication_full_fqun_cross_universe(
    validate_testdata_structural: ValidateTestdataStructural,
):
    implied_fqun = "mv:define-lang.org:implied_dup_implication"
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DuplicateQualityImplicationDiagnostic)
    assert diags[0].implication_name == f"position<{implied_fqun}:/foo>"
    assert diags[0].first_implication_line == 2
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert result.file_results[1].file_path == define_path.DefinePath("lib/foo.dfn")
    assert result.file_results[1].diagnostics == []


def test_implication_same_path_different_fquns_are_not_duplicates(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert_no_errors(result)


def test_duplicate_via_full_form_and_short_form_implication(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic)
    assert diags[0].fqun == "my.domain.com:my_lib"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 34


def test_implication_with_invalid_path_format_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38


def test_implication_invalid_name_does_not_become_duplicate(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38
    assert isinstance(diags[1], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[1].path == "/bad/"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 38


def test_invalid_implication_name_used_in_body_does_not_satisfy_chain_start(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 3
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/bad/"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 38
    assert isinstance(diags[1], diagnostics.UnknownGlobalNameDiagnostic)
    assert diags[1].source_global_name == "position</bad/>"
    assert diags[1].full_global_name == "position<my.domain.com:my_lib:/bad/>"
    assert diags[1].location.line == 6
    assert diags[1].location.column == 30
    assert isinstance(diags[2], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[2].path == "/bad/"
    assert diags[2].location.line == 6
    assert diags[2].location.column == 43


def test_circular_implication_emits_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("bar.dfn")
    diags = result.file_results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "action<my.domain.com:my_lib:/test>",
        "action<my.domain.com:my_lib:/bar>",
        "action<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 2
    assert diags[0].location.column == 25


def test_unused_implication_in_constructor_error(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    diags = result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</valid/minimal_position>"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 25
    assert diags[0].location.end_line == 2
    assert diags[0].location.end_column == 58
    assert diags[0].location.file_path == PurePosixPath("test.dfn")


def test_unused_implication_on_action_error(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_implication_used_only_in_constraint_block_is_unused(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</foo>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_two_implication_one_used_one_unused(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnusedQualityImplicationDiagnostic)
    assert diags[0].implication_name == "position</bar>"
    assert diags[0].location.line == 5
    assert diags[0].location.column == 25


def test_implication_for_nonexistent_quality_used_in_body(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].file_path == "nonexistent.dfn"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 34
