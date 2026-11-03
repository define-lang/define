# pyright: reportUnusedCallResult=false
"""Cross-FQUN global name walking validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast, config
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.compiler.validator.test_helpers import assert_no_errors

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateTestdataStructural

_PARENT_UNIVERSE = "mv:define-lang.org:parent_universe"
_CHILD_UNIVERSE = "mv:define-lang.org:child_universe"


def test_authority_conflict(
    validate_testdata_structural: ValidateTestdataStructural,
):
    assert_no_errors(validate_testdata_structural())


def test_references_across_fquns(
    validate_testdata_structural: ValidateTestdataStructural,
):
    assert_no_errors(validate_testdata_structural())


def test_sub_root_redeclares_parent_fqun(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.DuplicateFqunError)
    assert error.fqun == "mv:define-lang.org:parent"
    assert error.existing_config == define_path.DefinePath(
        ".define/project/config.defcl"
    )
    assert error.new_config == define_path.DefinePath(
        "lib/nested/.define/project/config.defcl"
    )
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("lib/target.dfn"),
    ]
    assert result.all_diagnostics == []


def test_cross_fqun_walks_into_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.file_results) == 2
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")


def test_direct_nested_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural(max_workers=1)
    assert len(result.file_results) == 4
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib/inner/target.dfn"
    )
    assert result.file_results[2].file_path == define_path.DefinePath(
        "ordinary/target.dfn"
    )
    assert result.file_results[3].file_path == define_path.DefinePath(
        "lib/inner/leaf.dfn"
    )


def test_same_universe_reference_in_ordinary_directory(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.file_results) == 2
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath(
        "ordinary/target.dfn"
    )


def test_cross_fqun_file_not_found(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert diags[0].file_path == "lib/missing.dfn"


def test_cross_fqun_sub_root_missing_config(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.NotProjectRootError)
    assert error.config_path == PurePosixPath("lib/.define/project/config.defcl")
    assert error.root == "lib"
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
    ]
    assert result.all_diagnostics == []


def test_cross_fqun_sub_root_missing_config_across_files_reports_one_config_error(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.NotProjectRootError)
    assert error.config_path == PurePosixPath("lib/.define/project/config.defcl")
    assert error.root == "lib"
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("other.dfn"),
    ]
    assert result.all_diagnostics == []


def test_cross_fqun_sub_root_fqun_mismatch(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.SubRootFqunMismatchError)
    assert error.expected_fqun == _CHILD_UNIVERSE
    assert error.actual_fqun == "mv:define-lang.org:actual_child"
    assert error.sub_root_path == "lib"
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
    ]
    assert result.all_diagnostics == []


def test_second_universe_declared_at_same_sub_root_path(
    validate_testdata_structural: ValidateTestdataStructural,
):
    deps_path = PurePosixPath(".define/deps/local.defcl")
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.SubRootPathAlreadyDeclaredError)
    assert error.sub_root_path == "lib"
    assert error.entry == config.LocalDependencyEntry(
        deps_path, "mv:define-lang.org:second_child", "lib"
    )
    assert error.existing_entry == config.LocalDependencyEntry(
        deps_path, _CHILD_UNIVERSE, "lib"
    )
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("lib/target.dfn"),
    ]
    assert result.all_diagnostics == []


def test_conflicting_sub_root_declaration_leaves_first_universe_usable(
    validate_testdata_structural: ValidateTestdataStructural,
):
    deps_path = PurePosixPath(".define/deps/local.defcl")
    result = validate_testdata_structural(max_workers=1)
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.SubRootPathAlreadyDeclaredError)
    assert error.sub_root_path == "lib"
    assert error.entry == config.LocalDependencyEntry(
        deps_path, "mv:define-lang.org:second_child", "lib"
    )
    assert error.existing_entry == config.LocalDependencyEntry(
        deps_path, _CHILD_UNIVERSE, "lib"
    )
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("second_child_reference.dfn"),
        define_path.DefinePath("lib/a.dfn"),
        define_path.DefinePath("lib/b.dfn"),
    ]
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].diagnostics == []
    cycle_diags = result.file_results[3].diagnostics
    assert len(cycle_diags) == 1
    assert isinstance(cycle_diags[0], diagnostics.CircularGlobalReferenceDiagnostic)
    assert cycle_diags[0].location.file_path == PurePosixPath("lib/b.dfn")
    assert cycle_diags[0].location.line == 3
    assert cycle_diags[0].location.column == 20
    assert cycle_diags[0].cycle == [
        "position<mv:define-lang.org:child_universe:/a>",
        "position<mv:define-lang.org:child_universe:/b>",
        "position<mv:define-lang.org:child_universe:/a>",
    ]


def test_path_inside_other_universe_before_its_sub_root_loads(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("lib/sub_root_target.dfn"),
    ]
    assert result.file_results[1].diagnostics == []
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    path_diag = diags[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.location.file_path == PurePosixPath("test.dfn")
    assert path_diag.location.line == 5
    assert path_diag.location.column == 29
    assert path_diag.path == "lib/parent_target.dfn"
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"


def test_sub_root_path_declared_by_outer_project_wins(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.SubRootPathAlreadyDeclaredError)
    assert error.sub_root_path == "p/lib"
    assert error.entry == config.LocalDependencyEntry(
        PurePosixPath("p/.define/deps/local.defcl"),
        "mv:define-lang.org:inner_lib",
        "lib",
    )
    assert error.existing_entry == config.LocalDependencyEntry(
        PurePosixPath(".define/deps/local.defcl"),
        "mv:define-lang.org:outer_lib",
        "p/lib",
    )
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("p/target.dfn"),
    ]
    assert result.all_diagnostics == []


def test_reference_naming_universe_into_its_declared_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
    ]
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    path_diag = diags[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.location.file_path == PurePosixPath("test.dfn")
    assert path_diag.location.line == 5
    assert path_diag.location.column == 29
    assert path_diag.path == "lib/inner/x.dfn"
    assert path_diag.other_universe == "mv:define-lang.org:grandchild"
    assert path_diag.sub_root_path == "lib/inner"


def test_sub_root_is_current_universe(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.LocalDependencyOnOwnUniverseError)
    assert error.entry == config.LocalDependencyEntry(
        PurePosixPath(".define/deps/local.defcl"),
        "mv:define-lang.org:test_parent",
        "lib",
    )
    assert result.all_exceptions == [error]
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].exception is None
    all_diags = result.all_diagnostics
    assert len(all_diags) == 3
    assert isinstance(all_diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert all_diags[0].file_path == "lib/target.dfn"
    assert (
        all_diags[0].definition_name
        == "position<mv:define-lang.org:test_parent:/lib/target>"
    )
    assert all_diags[0].location.line == 3
    assert all_diags[0].location.column == 29
    assert all_diags[0].location.end_line == 3
    assert all_diags[0].location.end_column == 39
    assert all_diags[0].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[1], diagnostics.ReferencedFileNotFoundDiagnostic)
    assert all_diags[1].file_path == "target.dfn"
    assert all_diags[1].location.line == 4
    assert all_diags[1].location.column == 29
    assert all_diags[1].location.end_line == 4
    assert all_diags[1].location.end_column == 35
    assert all_diags[1].location.file_path == PurePosixPath("test.dfn")
    assert isinstance(all_diags[2], diagnostics.PathMismatchDiagnostic)
    assert all_diags[2].expected_path == "/lib/target"
    assert all_diags[2].actual_path == "/target"
    assert all_diags[2].location.line == 1
    assert all_diags[2].location.column == 62
    assert all_diags[2].location.end_line == 1
    assert all_diags[2].location.end_column == 68
    assert all_diags[2].location.file_path == PurePosixPath("lib/target.dfn")


def test_reference_after_path_inside_other_universe_is_still_validated(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
    ]
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    path_diag = diags[0]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.location.file_path == PurePosixPath("test.dfn")
    assert path_diag.location.line == 5
    assert path_diag.location.column == 29
    assert path_diag.path == "lib/parent_target.dfn"
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    not_found_diag = diags[1]
    assert isinstance(not_found_diag, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert not_found_diag.location.file_path == PurePosixPath("test.dfn")
    assert not_found_diag.location.line == 6
    assert not_found_diag.location.column == 29
    assert not_found_diag.file_path == "lib/missing_target.dfn"


def test_path_inside_other_universe(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.PathInsideOtherUniverseDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].location.file_path == PurePosixPath(
        "test.dfn"
    )
    assert result.file_results[0].diagnostics[0].path == "lib/parent_target.dfn"
    assert result.file_results[0].diagnostics[0].location.line == 4
    assert result.file_results[0].diagnostics[0].location.column == 29
    assert result.file_results[0].diagnostics[0].path.endswith("lib/parent_target.dfn")
    assert result.file_results[0].diagnostics[0].other_universe == _CHILD_UNIVERSE
    assert result.file_results[0].diagnostics[0].sub_root_path == "lib"
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib/sub_root_target.dfn"
    )
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_path_inside_other_universe_skips_further_validation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 2
    wrong_type_diag = result.file_results[0].diagnostics[0]
    assert isinstance(
        wrong_type_diag, diagnostics.ReferencedDefinitionNotFoundDiagnostic
    )
    assert wrong_type_diag.location.file_path == PurePosixPath("test.dfn")
    assert wrong_type_diag.location.line == 3
    assert wrong_type_diag.location.column == 29
    assert wrong_type_diag.file_path == "lib/child_action.dfn"
    assert (
        wrong_type_diag.definition_name
        == "position<mv:define-lang.org:child_universe:/child_action>"
    )
    path_diag = result.file_results[0].diagnostics[1]
    assert isinstance(path_diag, diagnostics.PathInsideOtherUniverseDiagnostic)
    assert path_diag.location.file_path == PurePosixPath("test.dfn")
    assert path_diag.path == "lib/child_action.dfn"
    assert path_diag.location.line == 4
    assert path_diag.location.column == 29
    assert path_diag.path.endswith("lib/child_action.dfn")
    assert path_diag.other_universe == _CHILD_UNIVERSE
    assert path_diag.sub_root_path == "lib"
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib/child_action.dfn"
    )
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_cross_fqun_file_wrong_fqun_in_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    wrong_fqun = "mv:define-lang.org:totally_wrong"
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedDefinitionNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].location.file_path == PurePosixPath(
        "test.dfn"
    )
    assert result.file_results[0].diagnostics[0].location.line == 3
    assert result.file_results[0].diagnostics[0].location.column == 29
    assert result.file_results[0].diagnostics[0].file_path == "lib/target.dfn"
    assert (
        result.file_results[0].diagnostics[0].definition_name
        == "position<mv:define-lang.org:child_universe:/target>"
    )
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].exception is None
    assert len(result.file_results[1].diagnostics) == 1
    assert isinstance(
        result.file_results[1].diagnostics[0], diagnostics.FqunMismatchDiagnostic
    )
    assert result.file_results[1].diagnostics[0].location.file_path == PurePosixPath(
        "lib/target.dfn"
    )
    assert result.file_results[1].diagnostics[0].location.line == 1
    assert result.file_results[1].diagnostics[0].location.column == 31
    assert result.file_results[1].diagnostics[0].expected == _CHILD_UNIVERSE
    assert result.file_results[1].diagnostics[0].actual == wrong_fqun


def test_cross_fqun_wrong_type_in_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    assert len(result.file_results[0].diagnostics) == 1
    assert isinstance(
        result.file_results[0].diagnostics[0],
        diagnostics.ReferencedDefinitionNotFoundDiagnostic,
    )
    assert result.file_results[0].diagnostics[0].location.file_path == PurePosixPath(
        "test.dfn"
    )
    assert result.file_results[0].diagnostics[0].location.line == 3
    assert result.file_results[0].diagnostics[0].location.column == 29
    assert result.file_results[0].diagnostics[0].file_path == "lib/target.dfn"
    assert (
        result.file_results[0].diagnostics[0].definition_name
        == "position<mv:define-lang.org:child_universe:/target>"
    )
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_same_fqun_reference_inside_sub_root(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath("lib/entry.dfn")
    assert result.file_results[2].file_path == define_path.DefinePath("lib/leaf.dfn")


def test_cross_fqun_nested_sub_roots(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 3
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[2].file_path == define_path.DefinePath(
        "lib/inner/leaf.dfn"
    )


def test_partial_sub_root_failure_still_validates_successful_sub_roots(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.NotProjectRootError)
    assert error.config_path == PurePosixPath("lib_b/.define/project/config.defcl")
    assert error.root == "lib_b"
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("lib_a/target_a.dfn"),
    ]
    assert result.all_diagnostics == []


def test_partial_local_deps_missing_still_validates_configured_sub_roots(
    validate_testdata_structural: ValidateTestdataStructural,
):
    child_b = "mv:define-lang.org:child_b"
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    assert result.file_results[0].exception is None
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert diags[0].universe == child_b
    assert diags[0].current_universe_name == _PARENT_UNIVERSE
    assert result.file_results[1].file_path == define_path.DefinePath(
        "lib_a/target_a.dfn"
    )
    assert result.file_results[1].exception is None
    assert result.file_results[1].diagnostics == []


def test_failed_root_discovery_does_not_skip_remaining_files(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.NotProjectRootError)
    assert error.config_path == PurePosixPath("lib/.define/project/config.defcl")
    assert error.root == "lib"
    assert result.all_exceptions == [error]
    assert [file_result.file_path for file_result in result.file_results] == [
        define_path.DefinePath("test.dfn"),
        define_path.DefinePath("local.dfn"),
    ]
    assert result.all_diagnostics == []


def test_failed_root_edge_does_not_skip_remaining_edge_validation(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert len(result.config_errors) == 1
    error = result.config_errors[0]
    assert isinstance(error, config.NotProjectRootError)
    assert error.config_path == PurePosixPath("lib/.define/project/config.defcl")
    assert error.root == "lib"
    assert result.all_exceptions == [error]
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReferencedDefinitionNotFoundDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].file_path == "wrong_type.dfn"
    assert (
        diags[0].definition_name
        == "position<mv:define-lang.org:parent_universe:/wrong_type>"
    )
    assert diags[0].location.line == 4
    assert diags[0].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("wrong_type.dfn")
    assert result.file_results[1].diagnostics == []


def test_invalid_cross_fqun_reference_and_definition_in_one_file(
    validate_testdata_structural: ValidateTestdataStructural,
):
    foreign_universe = "mv:define-lang.org:other_lib"
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].location.line == 3
    assert diags[0].location.column == 31
    assert diags[0].expected == _PARENT_UNIVERSE
    assert diags[0].actual == foreign_universe
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].location.file_path == PurePosixPath("test.dfn")
    assert diags[1].location.line == 6
    assert diags[1].location.column == 29
    assert diags[1].universe == foreign_universe
    assert diags[1].current_universe_name == _PARENT_UNIVERSE


def test_same_path_in_known_and_unknown_universes_still_walks_into_known(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 2
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
    diags = result.file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].universe == "unknown.com:other_lib"
    assert diags[0].current_universe_name == _PARENT_UNIVERSE
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert result.file_results[1].file_path == define_path.DefinePath("lib/target.dfn")
    assert result.file_results[1].root_prefix == define_path.DefinePath("lib")
    assert result.file_results[1].diagnostics == []


def test_same_path_in_two_unknown_universes_diagnoses_each(
    validate_testdata_structural: ValidateTestdataStructural,
):
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    diags = result.file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[0].location.file_path == PurePosixPath("test.dfn")
    assert diags[0].universe == "unknown.com:lib_a"
    assert diags[0].current_universe_name == _PARENT_UNIVERSE
    assert diags[0].location.line == 3
    assert diags[0].location.column == 29
    assert isinstance(diags[1], diagnostics.ExternalUniverseNotConfiguredDiagnostic)
    assert diags[1].location.file_path == PurePosixPath("test.dfn")
    assert diags[1].universe == "unknown.com:lib_b"
    assert diags[1].current_universe_name == _PARENT_UNIVERSE
    assert diags[1].location.line == 4
    assert diags[1].location.column == 29


def test_same_path_in_two_known_universes_walks_into_both_sub_roots(
    validate_testdata_structural: ValidateTestdataStructural,
):
    child_x = "mv:define-lang.org:child_x"
    child_y = "mv:define-lang.org:child_y"
    result = validate_testdata_structural(max_workers=1)
    assert len(result.file_results) == 5
    assert_no_errors(result)
    assert result.file_results[0].file_path == define_path.DefinePath("test.dfn")
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


def test_unknown_universe_reported_once_for_same_file_references(
    validate_testdata_structural: ValidateTestdataStructural,
):
    foreign_universe = "mv:define-lang.org:other_lib"
    result = validate_testdata_structural()
    assert result.all_exceptions == []
    assert result.all_diagnostics == [
        diagnostics.FqunMismatchDiagnostic(
            location=ast.SourceLocation(
                line=2,
                column=31,
                end_line=2,
                end_column=58,
                file_path=PurePosixPath("test.dfn"),
            ),
            expected=_PARENT_UNIVERSE,
            actual=foreign_universe,
        ),
        diagnostics.PathMismatchDiagnostic(
            location=ast.SourceLocation(
                line=2,
                column=60,
                end_line=2,
                end_column=61,
                file_path=PurePosixPath("test.dfn"),
            ),
            expected_path="/test",
            actual_path="/a",
        ),
        diagnostics.FqunMismatchDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=31,
                end_line=3,
                end_column=58,
                file_path=PurePosixPath("test.dfn"),
            ),
            expected=_PARENT_UNIVERSE,
            actual=foreign_universe,
        ),
        diagnostics.PathMismatchDiagnostic(
            location=ast.SourceLocation(
                line=3,
                column=60,
                end_line=3,
                end_column=61,
                file_path=PurePosixPath("test.dfn"),
            ),
            expected_path="/test",
            actual_path="/b",
        ),
        diagnostics.ExternalUniverseNotConfiguredDiagnostic(
            location=ast.SourceLocation(
                line=6,
                column=29,
                end_line=6,
                end_column=56,
                file_path=PurePosixPath("test.dfn"),
            ),
            universe=foreign_universe,
            current_universe_name=_PARENT_UNIVERSE,
        ),
    ]
