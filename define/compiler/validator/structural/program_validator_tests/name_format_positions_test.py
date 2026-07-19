"""Name format position validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataNonFilesystem


def test_multiverse_name_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
    assert diags[0].multiverse_name == "_mv"
    assert diags[0].char == "_"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 34


def test_multiverse_name_too_short(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.MultiverseNameTooShortDiagnostic)
    assert diags[0].multiverse_name == "m"
    assert isinstance(diags[1], diagnostics.ReservedMultiverseNameDiagnostic)


def test_authority_domain_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
    assert diags[0].domain == "-example.com"
    assert diags[0].char == "-"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 46


def test_authority_domain_too_short(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.AuthorityDomainTooShortDiagnostic)
    assert diags[0].domain == "a"
    assert isinstance(diags[1], diagnostics.DotlessAuthorityDomainDiagnostic)


def test_authority_path_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
    assert diags[0].segment == ".hidden"
    assert diags[0].char == "."
    assert diags[0].location.line == 1
    assert diags[0].location.column == 48
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 55


def test_authority_path_empty_segment(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityPathEmptySegmentDiagnostic)
    assert diags[0].authority == "my.domain.com//team"


def test_universe_name_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
    assert diags[0].universe_name == "_my_lib"
    assert diags[0].char == "_"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 48
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 55


def test_universe_name_too_short(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UniverseNameTooShortDiagnostic)
    assert diags[0].universe_name == "t"


def test_path_segment_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "2bad"
    assert diags[0].char == "2"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 53
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 57


def test_global_name_path_empty_segment(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalNamePathEmptySegmentDiagnostic)
    assert diags[0].path == "/foo//bar"


def test_local_name_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    results = validate_testdata_non_filesystem().file_results
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "my-pos"
    assert diags[0].char == "-"
    assert diags[0].location.line == 2
    assert diags[0].location.column == 27
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[1].local_name == "my-pos"
    assert diags[1].char == "-"
    assert diags[1].location.line == 4
    assert diags[1].location.column == 24
