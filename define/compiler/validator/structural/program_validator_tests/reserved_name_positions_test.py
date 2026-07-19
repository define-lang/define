"""Reserved name position validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataStructuralNonFilesystem
from define.compiler.validator.structural import program_validator


def test_case_insensitive_reserved_universe_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    diags = validate_testdata_structural_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
    assert diags[0].universe_name == "STANDARD"
    assert diags[0].char == "S"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 50
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 58
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].reserved_name == "STANDARD"
    assert diags[1].location.line == 1
    assert diags[1].location.column == 50
    assert diags[1].location.end_line == 1
    assert diags[1].location.end_column == 58
    assert diags[1].location.file_path is None


def test_common_word_reserved_universe_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    diags = validate_testdata_structural_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "about"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 50
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 55
    assert diags[0].location.file_path is None


def test_define_reserved_universe_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    diags = validate_testdata_structural_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "define"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 50
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 56
    assert diags[0].location.file_path is None


def test_dotless_authority_with_multiverse_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    diags = validate_testdata_structural_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DotlessAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "nodot"
    assert diags[0].multiverse_name == "mv"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 39
    assert diags[0].location.file_path is None


def test_reserved_package_repository_multiverse_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    diags = validate_testdata_structural_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedMultiverseNameDiagnostic)
    assert diags[0].reserved_name == "npm"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 34
    assert diags[0].location.file_path is None


def test_reserved_universe_name_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "standard"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_reserved_universe_name_with_authority_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "example.com"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].reserved_name == "example"
    assert diags[1].location.line == 1
    assert diags[1].location.column == 43


def test_reserved_authority_position():
    source = "define the potential position<example.com:my_lib:/path>.\n"
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(source)
        .file_results
    )
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "example.com"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_reserved_authority_with_multiverse_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "example.com"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34


def test_dotless_authority_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DotlessAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "localhost"
    assert diags[0].multiverse_name == "local"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_reserved_multiverse_position(
    validate_testdata_structural_non_filesystem: ValidateTestdataStructuralNonFilesystem,
):
    results = validate_testdata_structural_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedMultiverseNameDiagnostic)
    assert diags[0].reserved_name == "python"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
