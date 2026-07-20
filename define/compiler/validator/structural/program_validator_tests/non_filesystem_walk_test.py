# pyright: reportUnusedCallResult=false
"""Non-filesystem cross-file walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

import pytest

from define.compiler import config, diagnostics
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.data_structures import define_path
from define.compiler.validator.test_helpers import assert_no_errors


def test_external_universe_no_project_config(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(
        diags[0], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].config_path == ".define/project/config.defcl"


def test_config_failure_still_validates_same_file_cycles(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert diags[0].location.line == 9
    assert diags[0].location.column == 20
    assert diags[0].cycle == [
        "position<my.domain.com:my_lib:/a>",
        "position<my.domain.com:my_lib:/b>",
        "position<my.domain.com:my_lib:/a>",
    ]
    assert isinstance(
        diags[1], diagnostics.NoProjectRootInNonFilesystemContextDiagnostic
    )
    assert diags[1].location.line == 3
    assert diags[1].location.column == 29
    assert diags[1].universe == "other.example.com:other_universe"


def test_external_universe_without_local_deps(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_external_universe_not_in_local_deps(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].universe == "other.example.com:other_universe"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"


def test_external_universe_invalid_local_deps(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[0].error, config.ConfigValidationError)


def test_external_universe_configured_but_no_sub_root_config(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[0].error, config.NotProjectRootError)


def test_partial_local_deps_missing_still_validates_configured_sub_roots_non_filesystem(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    child_b = "mv:define-lang.org:child_b"
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 2
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert diags[0].universe == child_b
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert result.file_results[1].file_path.name == "target_a.dfn"
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_duplicate_unknown_universe_non_filesystem_does_not_skip_remaining(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].location.line == 5
    assert diags[1].location.column == 29


def test_non_filesystem_reference_walks_into_sub_root(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[2].file_path == define_path.DefinePath("lib/leaf.dfn")
    assert result.file_results[2].root_prefix == define_path.DefinePath("lib")


def test_non_filesystem_cross_universe_reference(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    diag = result.file_results[0].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag.file_path == "lib/missing.dfn"
    assert diag.location.line == 4
    assert diag.location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_unknown_universe_does_not_block_known_universe_for_same_path(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 2
    assert str(result.file_results[0].file_path) == "<string>"
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:other_lib"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].diagnostics == []


def test_unknown_universe_and_sub_root_config_errors_in_source_order(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ConfigLoadErrorDiagnostic)
    assert isinstance(diags[0].error, config.NotProjectRootError)
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:other_lib"
    assert diags[1].current_universe_name == "my.domain.com:my_lib"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29


def test_two_unknown_universes_for_same_path_each_diagnosed(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].current_universe_name == "my.domain.com:my_lib"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].current_universe_name == "my.domain.com:my_lib"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29


def test_two_known_universes_for_same_path_each_load_their_file(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    child_x = "mv:define-lang.org:child_x"
    child_y = "mv:define-lang.org:child_y"
    result = validate_testdata_structural_non_filesystem(max_workers=1)
    assert len(result.file_results) == 5
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib_x/target.dfn"
    )
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib_x")
    assert (
        result.file_results[1]
        .definition_results[0]
        .definition.typed_name.full_typed_name
        == f"position<{child_x}:/target>"
    )
    assert result.file_results[2].file_path == define_path.DefinePath(
        "lib_y/target.dfn"
    )
    assert result.file_results[2].root_prefix == define_path.DefinePath("lib_y")
    assert (
        result.file_results[2]
        .definition_results[0]
        .definition.typed_name.full_typed_name
        == f"position<{child_y}:/target>"
    )
    assert result.file_results[3].file_path == define_path.DefinePath(
        "lib_x/x_child.dfn"
    )
    assert result.file_results[4].file_path == define_path.DefinePath(
        "lib_y/y_child.dfn"
    )


def test_forward_reference_within_non_filesystem_source_is_broken(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    diag = diags[0]
    assert isinstance(diag, diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diag.universe == "my.domain.com:my_lib"
    assert diag.current_universe_name == "my.domain.com:my_lib"
    assert diag.location.line == 7
    assert diag.location.column == 29


@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason=(
        "Non-filesystem resolution routes every reference through local deps,"
        " and a project's own universe is never among its local deps, so a"
        " current-universe reference is diagnosed as an unconfigured external"
        " universe instead of resolving to the file on disk."
    ),
)
def test_non_filesystem_reference_walks_into_current_universe_file(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert str(result.file_results[0].file_path) == "<string>"
    assert result.file_results[1].file_path == define_path.DefinePath("target.dfn")
    assert result.file_results[2].file_path == define_path.DefinePath("leaf.dfn")


@pytest.mark.xfail(
    raises=KeyError,
    strict=True,
    reason=(
        "In non-filesystem mode, no project root is registered with the"
        " path_tracker, so a back-reference to an in-source cross-universe"
        " definition crashes in program_validator._resolve_target_file when"
        " path_tracker.has_sub_root looks up the empty parent root in"
        " self._project_roots and raises KeyError."
    ),
)
def test_non_filesystem_cross_universe_back_reference(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    result = validate_testdata_structural_non_filesystem()
    assert result.all_exceptions == []
