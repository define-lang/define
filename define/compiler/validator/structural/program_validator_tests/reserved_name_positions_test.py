"""Reserved name position validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataNonFilesystem
from define.compiler.validator.structural import program_validator


def test_reserved_universe_name_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].reserved_name == "standard"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_reserved_universe_name_with_authority_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
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
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "example.com"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34


def test_dotless_authority_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DotlessAuthorityDomainDiagnostic)
    assert diags[0].reserved_name == "localhost"
    assert diags[0].multiverse_name == "local"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31


def test_reserved_multiverse_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedMultiverseNameDiagnostic)
    assert diags[0].reserved_name == "python"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
