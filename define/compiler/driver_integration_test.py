# Dear Agent: It is okay for this test file to have this docstring.
"""
Integration tests for the driver.

This is a generalized integration test that attempts to catch all the
errors that the compiler could throw. However, it is less specific
in its assertions (and thus harder to debug) than the more specific unit
tests. As such, when adding a new language feature, always add a more-specific
unit test for it in the parser or the validator (or whevever most appropriate).

This test works by walking through all the files in testdata/ and generating
a test for each one of them. Simply adding a file to testdata will cause a new
test to be generated here. For tests that produce validator diagnostics (instead
of parser exceptions) you will have to update the EXPECTED_FILE_DIAGNOSTICS or
EXPECTED_PROJECT_DIAGNOSTICS table. Files not listed in EXPECTED_FILE_DIAGNOSTICS
are expected to produce DefineSyntaxError.
"""

from pathlib import Path

import pytest

from define.compiler import diagnostics, driver, parser_exceptions, validator

TESTDATA_ROOT = Path("define/testdata")
FILES_ROOT = TESTDATA_ROOT / "files"
PROJECTS_ROOT = TESTDATA_ROOT / "projects"

VALID_FILES = sorted((FILES_ROOT / "valid").glob("*.def"))
INVALID_SYNTAX_FILES = sorted((FILES_ROOT / "invalid" / "syntax").rglob("*.def"))

# Key: path relative to FILES_ROOT / "invalid" / "syntax" (as posix string)
# Value: list of expected diagnostic types in order
# Files NOT in this dict are expected to produce DefineSyntaxError.
EXPECTED_FILE_DIAGNOSTICS: dict[str, list[type[diagnostics.Diagnostic]]] = {
    "authority_path_empty_segment/empty_segment.def": [
        diagnostics.AuthorityPathEmptySegmentDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "fqun_format/universe_uppercase.def": [
        diagnostics.UniverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "fqun_validation/universe_without_authority.def": [
        diagnostics.UniverseWithoutAuthorityDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_leading_dot.def": [
        diagnostics.AuthorityDomainInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_leading_hyphen.def": [
        diagnostics.AuthorityDomainInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_single_char.def": [
        diagnostics.AuthorityDomainTooShortDiagnostic,
        diagnostics.DotlessAuthorityDomainDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_trailing_dot.def": [
        diagnostics.AuthorityDomainInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_trailing_hyphen.def": [
        diagnostics.AuthorityDomainInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_domain/authority_uppercase.def": [
        diagnostics.AuthorityDomainInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_authority_path_segment/authority_path_leading_dot.def": [
        diagnostics.InvalidAuthorityPathSegmentDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_global_name_path/hyphen.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_global_name_path/leading_digit.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_global_name_path/path_leading_digit.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_global_name_path/path_uppercase.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_global_name_path/special_characters.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_global_name_path/uppercase_letter.def": [
        diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "invalid_multiverse_name/multiverse_leading_underscore.def": [
        diagnostics.MultiverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_multiverse_name/multiverse_single_char.def": [
        diagnostics.MultiverseNameTooShortDiagnostic,
        diagnostics.ReservedMultiverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_multiverse_name/multiverse_trailing_underscore.def": [
        diagnostics.MultiverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_multiverse_name/multiverse_uppercase.def": [
        diagnostics.MultiverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_universe_name_format/universe_leading_underscore.def": [
        diagnostics.UniverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_universe_name_format/universe_single_char.def": [
        diagnostics.UniverseNameTooShortDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "invalid_universe_name_format/universe_trailing_underscore.def": [
        diagnostics.UniverseNameInvalidCharDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "local_names/duplicate.def": [diagnostics.LocalNameConflictDiagnostic],
    "local_names/duplicate_across_scopes.def": [
        diagnostics.LocalNameConflictDiagnostic,
    ],
    "local_names/duplicate_inner_scope.def": [
        diagnostics.LocalNameConflictDiagnostic,
    ],
    "local_names/hyphen.def": [diagnostics.InvalidLocalNameFormatDiagnostic],
    "local_names/leading_digit.def": [diagnostics.InvalidLocalNameFormatDiagnostic],
    "local_names/space.def": [diagnostics.InvalidLocalNameFormatDiagnostic],
    "local_names/special_characters.def": [
        diagnostics.InvalidLocalNameFormatDiagnostic,
    ],
    "local_names/uppercase.def": [diagnostics.InvalidLocalNameFormatDiagnostic],
    "paths/double_slash.def": [
        diagnostics.GlobalNamePathEmptySegmentDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "paths/empty_path.def": [
        diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "paths/missing_leading_slash.def": [
        diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "paths/path_leading_underscore.def": [diagnostics.PathMismatchDiagnostic],
    "paths/trailing_slash.def": [
        diagnostics.GlobalNamePathTrailingSlashDiagnostic,
        diagnostics.PathMismatchDiagnostic,
    ],
    "reserved_names/reserved_authority_example_com.def": [
        diagnostics.ReservedAuthorityDomainDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_authority_no_dot_local.def": [
        diagnostics.ReservedMultiverseNameDiagnostic,
        diagnostics.DotlessAuthorityDomainDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_authority_no_dot_mv.def": [
        diagnostics.DotlessAuthorityDomainDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_multiverse_language.def": [
        diagnostics.ReservedMultiverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_multiverse_package_repo.def": [
        diagnostics.ReservedMultiverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_universe_case_insensitive.def": [
        diagnostics.UniverseNameInvalidCharDiagnostic,
        diagnostics.ReservedUniverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_universe_common_word.def": [
        diagnostics.ReservedUniverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_universe_define.def": [
        diagnostics.ReservedUniverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_universe_example.def": [
        diagnostics.ReservedUniverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "reserved_names/reserved_universe_standard.def": [
        diagnostics.ReservedUniverseNameDiagnostic,
        diagnostics.FqunMismatchDiagnostic,
    ],
    "short_form_required/full_form_same_fqun.def": [
        diagnostics.GlobalReferenceMustUseShortFormDiagnostic,
    ],
}

# Key: path relative to PROJECTS_ROOT / "invalid" (as posix string)
EXPECTED_PROJECT_DIAGNOSTICS: dict[str, list[type[diagnostics.Diagnostic]]] = {
    "global_name_walk_wrong_type": [
        diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    ],
    "syntax/duplicate_definitions": [diagnostics.DuplicateDefinitionDiagnostic],
    "syntax/fqun_mismatch": [diagnostics.FqunMismatchDiagnostic],
    "syntax/path_mismatch": [diagnostics.PathMismatchDiagnostic],
    "syntax/universe_uppercase": [diagnostics.UniverseNameInvalidCharDiagnostic],
}

EXPECTED_PROJECT_EXCEPTIONS: dict[str, type[Exception]] = {
    "global_name_walk_missing": FileNotFoundError,
}


def discover_projects(base_dir: Path) -> list[Path]:
    """Discover all Define project directories."""
    projects: list[Path] = []
    for config_file in base_dir.rglob("config.defcl"):
        if ".define/project" in str(config_file):
            project_dir = config_file.parent.parent.parent
            projects.append(project_dir)
    return sorted(projects)


VALID_PROJECTS = discover_projects(PROJECTS_ROOT / "valid")
INVALID_PROJECTS = discover_projects(PROJECTS_ROOT / "invalid")
PROJECT_CUSTOM_ENTRY_POINTS: dict[str, str] = {
    "invalid/syntax/path_mismatch": "correct_path/test.def",
    "valid/nested_paths": "nested/deep/test.def",
}


def test_lists_not_empty():
    assert VALID_PROJECTS
    assert INVALID_PROJECTS
    assert VALID_FILES
    assert INVALID_SYNTAX_FILES


def project_entrypoint(project_dir: Path) -> Path:
    """Return the .def entrypoint that should be validated for a project."""
    project_rel_path = project_dir.relative_to(PROJECTS_ROOT).as_posix()
    custom_entrypoint = PROJECT_CUSTOM_ENTRY_POINTS.get(project_rel_path)
    if custom_entrypoint is not None:
        return Path(custom_entrypoint)
    return Path("test.def")


def _all_diagnostics(
    results: list[validator.ValidationResult],
) -> list[diagnostics.Diagnostic]:
    diags: list[diagnostics.Diagnostic] = []
    for result in results:
        diags.extend(result.diagnostics)
    return diags


@pytest.mark.parametrize(
    "def_file",
    [f.relative_to(FILES_ROOT) for f in VALID_FILES],
    ids=[f.name for f in VALID_FILES],
)
def test_valid_files(def_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that valid files in files/valid/ parse successfully."""
    monkeypatch.chdir(FILES_ROOT)

    results = driver.Driver().validate_program(def_file)
    assert all(not result.diagnostics for result in results)
    assert all(result.exception is None for result in results)


@pytest.mark.parametrize(
    "def_file",
    [f.relative_to(FILES_ROOT) for f in INVALID_SYNTAX_FILES],
    ids=[
        f.relative_to(FILES_ROOT / "invalid" / "syntax").as_posix()
        for f in INVALID_SYNTAX_FILES
    ],
)
def test_invalid_syntax_files(def_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid syntax files produce syntax errors or validation diagnostics."""
    monkeypatch.chdir(FILES_ROOT)
    d = driver.Driver()
    rel_key = def_file.relative_to(Path("invalid/syntax")).as_posix()

    expected_types = EXPECTED_FILE_DIAGNOSTICS.get(rel_key)
    if expected_types is not None:
        results = d.validate_program(def_file)
        assert all(result.exception is None for result in results)
        all_diags = _all_diagnostics(results)
        assert [type(diag) for diag in all_diags] == expected_types, (
            f"For {rel_key}: expected {[t.__name__ for t in expected_types]}, "
            f"got {[type(d).__name__ for d in all_diags]}"
        )
    else:
        results = d.validate_program(def_file)
        assert not _all_diagnostics(results)
        exceptions_seen = [
            result.exception for result in results if result.exception is not None
        ]
        assert exceptions_seen, "Expected at least one exception"
        assert all(
            isinstance(e, parser_exceptions.DefineSyntaxError) for e in exceptions_seen
        )


@pytest.mark.parametrize(
    "project_dir", VALID_PROJECTS, ids=[p.name for p in VALID_PROJECTS]
)
def test_valid_projects(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that valid projects produce no diagnostics."""
    monkeypatch.chdir(project_dir)

    d = driver.Driver()

    entry_point = project_entrypoint(project_dir)
    results = d.validate_program(entry_point)
    assert all(result.exception is None for result in results)
    assert all(not result.diagnostics for result in results)


@pytest.mark.parametrize(
    "project_dir",
    INVALID_PROJECTS,
    ids=[p.relative_to(PROJECTS_ROOT / "invalid").as_posix() for p in INVALID_PROJECTS],
)
def test_invalid_projects(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that invalid projects produce expected diagnostics."""
    monkeypatch.chdir(project_dir)

    d = driver.Driver()

    entry_point = project_entrypoint(project_dir)
    rel_key = project_dir.relative_to(PROJECTS_ROOT / "invalid").as_posix()
    expected_exception = EXPECTED_PROJECT_EXCEPTIONS.get(rel_key)
    results = d.validate_program(entry_point)
    if expected_exception is not None:
        exceptions_seen = [
            result.exception for result in results if result.exception is not None
        ]
        assert exceptions_seen, "Expected at least one exception"
        assert all(isinstance(e, expected_exception) for e in exceptions_seen)
        return

    assert all(result.exception is None for result in results)
    all_diags = _all_diagnostics(results)
    expected_types = EXPECTED_PROJECT_DIAGNOSTICS.get(rel_key)
    if expected_types is None:
        pytest.fail(
            f"Expected diagnostics for {rel_key} not specified. Got: {all_diags!r}"
        )

    assert [type(diag) for diag in all_diags] == expected_types, (
        f"For {rel_key}: expected {[t.__name__ for t in expected_types]}, "
        f"got {[type(d).__name__ for d in all_diags]}"
    )
