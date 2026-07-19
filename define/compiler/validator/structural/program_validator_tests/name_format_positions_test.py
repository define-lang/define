"""Name format position validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.conftest import ValidateTestdataNonFilesystem


def test_authority_domain_leading_dot_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
    assert diags[0].domain == ".define-lang.org"
    assert diags[0].char == "."
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 50
    assert diags[0].location.file_path is None


def test_authority_domain_trailing_dot_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
    assert diags[0].domain == "define-lang.org."
    assert diags[0].char == "."
    assert diags[0].location.line == 1
    assert diags[0].location.column == 49
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 50
    assert diags[0].location.file_path is None


def test_authority_domain_trailing_hyphen_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
    assert diags[0].domain == "define-lang.org-"
    assert diags[0].char == "-"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 49
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 50
    assert diags[0].location.file_path is None


def test_authority_domain_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
    assert diags[0].domain == "Define-lang.org"
    assert diags[0].char == "D"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 34
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 49
    assert diags[0].location.file_path is None


def test_global_name_path_hyphen_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "test-path"
    assert diags[0].char == "-"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 93
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 98
    assert diags[0].location.file_path is None


def test_global_name_path_special_character_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "test@path"
    assert diags[0].char == "@"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 93
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 98
    assert diags[0].location.file_path is None


def test_global_name_path_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "TestPath"
    assert diags[0].char == "T"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 89
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 97
    assert diags[0].location.file_path is None


def test_later_path_segment_leading_digit_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "9path"
    assert diags[0].char == "9"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 83
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 88
    assert diags[0].location.file_path is None


def test_local_name_leading_digit_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "1bad"
    assert diags[0].char == "1"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert diags[0].location.end_line == 3
    assert diags[0].location.end_column == 29
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[1].position_name == "position<1bad>"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 25
    assert diags[1].location.end_line == 3
    assert diags[1].location.end_column == 29
    assert diags[1].location.file_path is None


def test_local_name_special_character_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<my@pos>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert diags[0].location.end_line == 3
    assert diags[0].location.end_column == 31
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[1].local_name == "my@pos"
    assert diags[1].char == "@"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 27
    assert diags[1].location.end_line == 3
    assert diags[1].location.end_column == 31
    assert diags[1].location.file_path is None


def test_local_name_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "BadName"
    assert diags[0].char == "B"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25
    assert diags[0].location.end_line == 3
    assert diags[0].location.end_column == 32
    assert diags[0].location.file_path is None
    assert isinstance(diags[1], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[1].position_name == "position<BadName>"
    assert diags[1].location.line == 3
    assert diags[1].location.column == 25
    assert diags[1].location.end_line == 3
    assert diags[1].location.end_column == 32
    assert diags[1].location.file_path is None


def test_multiverse_trailing_underscore_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
    assert diags[0].multiverse_name == "mv_"
    assert diags[0].char == "_"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 33
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 34
    assert diags[0].location.file_path is None


def test_multiverse_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
    assert diags[0].multiverse_name == "Mv"
    assert diags[0].char == "M"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 31
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 33
    assert diags[0].location.file_path is None


def test_path_segment_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    assert diags[0].segment == "Path"
    assert diags[0].char == "P"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 83
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 87
    assert diags[0].location.file_path is None


def test_path_leading_underscore_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert diags == []


def test_path_trailing_slash_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
    assert diags[0].path == "/invalid/syntax/paths/trailing_slash/"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 97
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 98
    assert diags[0].location.file_path is None


def test_universe_trailing_underscore_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
    assert diags[0].universe_name == "test_files_"
    assert diags[0].char == "_"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 60
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 61
    assert diags[0].location.file_path is None


def test_universe_uppercase_position(
    validate_testdata_non_filesystem: ValidateTestdataNonFilesystem,
):
    diags = validate_testdata_non_filesystem().file_results[0].diagnostics
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
    assert diags[0].universe_name == "MY_LIB"
    assert diags[0].char == "M"
    assert diags[0].location.line == 1
    assert diags[0].location.column == 47
    assert diags[0].location.end_line == 1
    assert diags[0].location.end_column == 53
    assert diags[0].location.file_path is None


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
