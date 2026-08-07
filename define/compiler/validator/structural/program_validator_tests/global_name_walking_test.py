# pyright: reportUnusedCallResult=false
"""Global name walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import PurePosixPath
from unittest import mock

from define.compiler import diagnostics
from define.compiler.conftest import (
    ValidateTestdataStructural,
)
from define.compiler.data_structures import define_path
from define.compiler.validator.structural import file_validator
from define.compiler.validator.test_helpers import assert_no_errors


def test_nested_file_path(validate_testdata_structural: ValidateTestdataStructural):
    result = validate_testdata_structural(entry_file="sub/dir/leaf.dfn")
    assert len(result.file_results) == 1
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath(
        "sub/dir/leaf.dfn"
    )


def test_walk_returns_results_in_encounter_order(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert [r.file_path for r in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("middle.dfn"),
        define_path.DefinePath("leaf.dfn"),
    ]


def test_duplicate_does_not_corrupt_reference_resolution(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert result.all_exceptions == []
    assert len(result.file_results) == 3
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == define_path.DefinePath("dup.dfn")
    assert len(result.file_results[2].diagnostics) == 1
    assert isinstance(
        result.file_results[2].diagnostics[0], diagnostics.PathMismatchDiagnostic
    )
    assert result.file_results[2].diagnostics[0].location.line == 1
    assert result.file_results[2].diagnostics[0].location.column == 52
    assert result.file_results[2].diagnostics[0].expected_path == "/dup"
    assert result.file_results[2].diagnostics[0].actual_path == "/target"


def test_duplicate_source_definition_does_not_add_reference_edges(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    all_diags = result.all_diagnostics
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.DuplicateDefinitionDiagnostic)
    assert all_diags[0].definition_type == "position"
    assert all_diags[0].path == "/test"
    assert all_diags[0].first_definition_line == 1
    assert all_diags[0].location.line == 2
    assert all_diags[0].location.column == 1


def test_cross_file_duplicate_definition_reports_path_mismatch(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("other.dfn")
    diags = result.file_results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/other"
    assert diags[0].actual_path == "/test"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 70
    assert diags[0].location.end_line == 2
    assert diags[0].location.end_column == 75
    assert diags[0].location.file_path == PurePosixPath("other.dfn")


def test_back_reference_to_earlier_definition_does_not_load_its_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
    assert diags[0].expected_path == "/test"
    assert diags[0].actual_path == "/other"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 52


def test_same_target_file_referenced_as_two_types_loads_once(
    validate_testdata_structural: ValidateTestdataStructural,
):
    original_validate_file = file_validator.FileStructuralValidator.validate_file
    validated_paths: list[str] = []

    def recording_validate_file(
        self: file_validator.FileStructuralValidator,
        context: file_validator.FileValidationContext,
    ):
        validated_paths.append(str(context.full_path))
        return original_validate_file(self, context)

    with mock.patch.object(
        file_validator.FileStructuralValidator,
        "validate_file",
        autospec=True,
        side_effect=recording_validate_file,
    ):
        result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert validated_paths == ["test.dfn", "target.dfn"]
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].file_path == "target.dfn"
    assert diags[0].definition_name == "action<my.domain.com:my_lib:/target>"
    assert diags[0].location.line == 4
    assert diags[0].location.column == 27
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[1].diagnostics == []


def test_self_cycle_emits_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<my.domain.com:my_lib:/test>\n"
        + "  --> position<my.domain.com:my_lib:/test>"
    )


def test_two_file_cycle_emits_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == define_path.DefinePath("loop.dfn")
    assert result.file_results[1].exception is None
    diags = result.file_results[1].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<mv:define-lang.org:test_walk_cycle:/test>",
        "position<mv:define-lang.org:test_walk_cycle:/loop>",
        "position<mv:define-lang.org:test_walk_cycle:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert (
        diags[0].message
        == "circular references between definitions are not allowed in Define:\n"
        + "position<mv:define-lang.org:test_walk_cycle:/test>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/loop>\n"
        + "  --> position<mv:define-lang.org:test_walk_cycle:/test>"
    )


def test_shared_target_depth_increases_through_paths_of_different_lengths(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert_no_errors(result)


def test_cycle_path_search_skips_a_shared_definition_already_seen(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert result.all_exceptions == []
    diags = result.all_diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<mv:define-lang.org:coverage_cycle:/start>",
        "position<mv:define-lang.org:coverage_cycle:/left>",
        "position<mv:define-lang.org:coverage_cycle:/shared>",
        "position<mv:define-lang.org:coverage_cycle:/end>",
        "position<mv:define-lang.org:coverage_cycle:/start>",
    ]


def test_unknown_universe_emits_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_duplicate_unknown_universe_emits_one_diagnostic(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_unknown_universe_across_files_reported_per_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    all_diags = result.all_diagnostics
    assert len(all_diags) == 2
    for diag in all_diags:
        assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
        assert diag.location.line == 3
        assert diag.location.column == 29
        assert diag.universe == "other.example.com:other_universe"
        assert diag.current_universe_name == "my.domain.com:my_lib"


def test_already_tracked_discovery_does_not_skip_remaining_files(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert len(result.file_results) == 4
    assert [r.file_path for r in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("middle.dfn"),
        define_path.DefinePath("shared.dfn"),
        define_path.DefinePath("leaf.dfn"),
    ]
    assert_no_errors(result)


def test_circular_reference_does_not_skip_remaining_edge_validation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/test>",
        "position<my.domain.com:my_lib:/test>",
    ]
    assert diags[0].location.line == 3
    assert diags[0].location.column == 20
    assert isinstance(diags[1], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[1].file_path == "wrong_type.dfn"
    assert diags[1].definition_name == "position<my.domain.com:my_lib:/wrong_type>"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("wrong_type.dfn")
    assert result.file_results[1].diagnostics == []
