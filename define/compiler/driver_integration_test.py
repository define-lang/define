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
of parser exceptions) you will have to update the EXPECTED_DIAGNOSTIC_BY_SUBSTRING
table.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from define.compiler import diagnostics, driver, parser_exceptions, validator

TESTDATA_ROOT = Path("define/testdata")
FILES_ROOT = TESTDATA_ROOT / "files"
PROJECTS_ROOT = TESTDATA_ROOT / "projects"

VALID_FILES = sorted((FILES_ROOT / "valid").glob("*.def"))
INVALID_SYNTAX_FILES = sorted((FILES_ROOT / "invalid" / "syntax").rglob("*.def"))

# Substrings that indicate validation diagnostics (path/context) -> expected diagnostic type or None
# TODO: Refactor this to be per-test, and also check for all diagnostics we expect to be emitted.
EXPECTED_DIAGNOSTIC_BY_SUBSTRING: dict[str, type | None] = {
    "universe_uppercase": diagnostics.UniverseNameInvalidCharDiagnostic,
    "path_mismatch": diagnostics.PathMismatchDiagnostic,
    "fqun_mismatch": diagnostics.FqunMismatchDiagnostic,
    "duplicate_definitions": diagnostics.DuplicateDefinitionDiagnostic,
    "reserved_names/reserved_universe": diagnostics.ReservedUniverseNameDiagnostic,
    "reserved_names/reserved_authority_example_com": diagnostics.ReservedAuthorityDomainDiagnostic,
    "reserved_names/reserved_authority_no_dot": diagnostics.DotlessAuthorityDomainDiagnostic,
    "reserved_names/reserved_multiverse": diagnostics.ReservedMultiverseNameDiagnostic,
    "fqun_validation/universe_without_authority": diagnostics.UniverseWithoutAuthorityDiagnostic,
    "paths/path_leading_underscore": diagnostics.PathMismatchDiagnostic,
    "paths/missing_leading_slash": diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic,
    "paths/trailing_slash": diagnostics.GlobalNamePathTrailingSlashDiagnostic,
    "paths/double_slash": diagnostics.GlobalNamePathEmptySegmentDiagnostic,
    "paths/empty_path": diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic,
    "authority_path_empty_segment/": diagnostics.AuthorityPathEmptySegmentDiagnostic,
    "short_form_required/": diagnostics.GlobalReferenceMustUseShortFormDiagnostic,
    "terminators/missing_space_before_terminator": diagnostics.FqunMismatchDiagnostic,
    "invalid_authority_domain/authority_single_char": diagnostics.AuthorityDomainTooShortDiagnostic,
    "invalid_authority_domain/": diagnostics.AuthorityDomainInvalidCharDiagnostic,
    "invalid_authority_path_segment/": diagnostics.InvalidAuthorityPathSegmentDiagnostic,
    "invalid_global_name_path/": diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
    "invalid_multiverse_name/multiverse_single_char": diagnostics.MultiverseNameTooShortDiagnostic,
    "invalid_multiverse_name/": diagnostics.MultiverseNameInvalidCharDiagnostic,
    "invalid_universe_name_format/universe_single_char": diagnostics.UniverseNameTooShortDiagnostic,
    "invalid_universe_name_format/": diagnostics.UniverseNameInvalidCharDiagnostic,
    "local_names/duplicate": diagnostics.LocalNameConflictDiagnostic,
    "local_names/leading_digit": diagnostics.InvalidLocalNameFormatDiagnostic,
    "local_names/space": diagnostics.InvalidLocalNameFormatDiagnostic,
    "local_names/uppercase": diagnostics.InvalidLocalNameFormatDiagnostic,
    "local_names/hyphen": diagnostics.InvalidLocalNameFormatDiagnostic,
    "local_names/special_characters": diagnostics.InvalidLocalNameFormatDiagnostic,
    "global_name_walk_wrong_type": diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
}

EXPECTED_EXCEPTION_BY_SUBSTRING: dict[str, type[Exception]] = {
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


def _find_substring_mapping_match[T](
    mapping: Mapping[str, T], haystack: str
) -> T | None:
    return next(
        (value for substring, value in mapping.items() if substring in haystack), None
    )


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
    file_name = str(def_file)
    d = driver.Driver()

    expected_diagnostic = _find_substring_mapping_match(
        EXPECTED_DIAGNOSTIC_BY_SUBSTRING, file_name
    )
    if expected_diagnostic:
        results = d.validate_program(def_file)
        assert all(result.exception is None for result in results)
        all_diagnostics = _all_diagnostics(results)
        # TODO: Refactor to assert that all diagnostics are as expected.
        assert any(isinstance(diag, expected_diagnostic) for diag in all_diagnostics), (
            f"Expected {expected_diagnostic.__name__} for {file_name}"
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
    project_str = str(project_dir)
    expected_exception = _find_substring_mapping_match(
        EXPECTED_EXCEPTION_BY_SUBSTRING, project_str
    )
    results = d.validate_program(entry_point)
    if expected_exception is not None:
        exceptions_seen = [
            result.exception for result in results if result.exception is not None
        ]
        assert exceptions_seen, "Expected at least one exception"
        assert all(isinstance(e, expected_exception) for e in exceptions_seen)
        return

    assert all(result.exception is None for result in results)
    all_diagnostics = _all_diagnostics(results)
    expected_type = _find_substring_mapping_match(
        EXPECTED_DIAGNOSTIC_BY_SUBSTRING, project_str
    )
    if expected_type is None:
        pytest.fail(
            "Expected diagnostic for "
            + f"{entry_point} not specified. Got: {all_diagnostics!r}"
        )

    # TODO: Refactor to assert that all diagnostics are as expected.
    assert any(isinstance(diag, expected_type) for diag in all_diagnostics), (
        f"Expected {expected_type.__name__} for {entry_point}"
    )
