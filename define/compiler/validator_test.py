"""Tests for the Define language validator."""

from define.compiler import parser, validator
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()
_transformer = DefineTransformer()


def _parse_transform_validate(
    source: str, file_path: str | None = None
) -> list[validator.Diagnostic]:
    tree = _parser.parse(source)
    program = _transformer.transform(tree)
    return validator.Validator(program, source).validate(file_path=file_path)


def _check_diagnostic_format(
    diagnostic: validator.Diagnostic,
    source: str,
    expected_line: int,
    expected_column: int,
) -> None:
    source_lines = source.splitlines()
    formatted = diagnostic.format(source_lines)
    assert f"line {expected_line}, column {expected_column}" in formatted
    assert source_lines[expected_line - 1] in formatted
    lines = formatted.split("\n")
    caret_line = next(line for line in lines if "^" in line)
    assert caret_line.index("^") == expected_column + 1


class TestReservedUniverseNames:
    def test_standard_is_reserved(self):
        source = "define the potential position<standard:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedUniverseNameDiagnostic)
        assert diagnostics[0].reserved_name == "standard"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_example_is_reserved(self):
        source = "define the potential position<example.com:example:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 2
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert diagnostics[0].reserved_name == "example.com"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)
        assert isinstance(diagnostics[1], validator.ReservedUniverseNameDiagnostic)
        assert diagnostics[1].reserved_name == "example"
        _check_diagnostic_format(diagnostics[1], source, 1, 43)

    def test_common_word_is_reserved(self):
        source = "define the potential position<example.com:about:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 2
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert diagnostics[0].reserved_name == "example.com"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)
        assert isinstance(diagnostics[1], validator.ReservedUniverseNameDiagnostic)
        assert diagnostics[1].reserved_name == "about"
        _check_diagnostic_format(diagnostics[1], source, 1, 43)

    def test_case_insensitive_check(self):
        source = "define the potential position<example.com:STANDARD:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 3
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert diagnostics[0].reserved_name == "example.com"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)
        assert isinstance(diagnostics[1], validator.ReservedUniverseNameDiagnostic)
        assert diagnostics[1].reserved_name == "STANDARD"
        _check_diagnostic_format(diagnostics[1], source, 1, 43)
        assert isinstance(diagnostics[2], validator.UniverseNameUppercaseDiagnostic)
        assert diagnostics[2].universe_name == "STANDARD"

    def test_non_reserved_universe_name(self):
        source = "define the potential position<example.com:my_library:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert diagnostics[0].reserved_name == "example.com"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)


class TestReservedAuthorityNames:
    def test_example_com_is_reserved(self):
        source = "define the potential position<example.com:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert diagnostics[0].reserved_name == "example.com"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_authority_without_dot_in_local_multiverse(self):
        source = "define the potential position<localhost:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedAuthorityNameDiagnostic)
        assert "localhost" in diagnostics[0].reserved_name
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_authority_with_dot_in_local_multiverse_ok(self):
        source = "define the potential position<my.domain.com:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0


class TestReservedMultiverseNames:
    def test_mv_is_allowed(self):
        source = "define the potential position<mv:example.org:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0

    def test_programming_language_is_reserved(self):
        source = "define the potential position<python:example.org:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedMultiverseNameDiagnostic)
        assert diagnostics[0].reserved_name == "python"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_package_repository_is_reserved(self):
        source = "define the potential position<npm:example.org:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedMultiverseNameDiagnostic)
        assert diagnostics[0].reserved_name == "npm"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)


class TestDiagnosticCollection:
    def test_multiple_diagnostics_collected(self):
        source = (
            "define the potential position<standard:/first>.\n"
            "define the potential position<standard:/second>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 2
        _check_diagnostic_format(diagnostics[0], source, 1, 31)
        _check_diagnostic_format(diagnostics[1], source, 2, 31)

    def test_diagnostics_in_source_order(self):
        source = (
            "define the potential position<standard:/first>.\n"
            "define the potential position<standard:/second>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert diagnostics[0].position.line == 1
        assert diagnostics[1].position.line == 2


class TestPathMismatch:
    def test_path_matches_file_no_error(self):
        source = "define the potential position<my.domain.com:my_lib:/foo/bar>.\n"
        diagnostics = _parse_transform_validate(source, file_path="foo/bar")
        assert len(diagnostics) == 0

    def test_path_mismatch_error(self):
        source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
        diagnostics = _parse_transform_validate(source, file_path="foo/bar")
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.PathMismatchDiagnostic)
        assert diagnostics[0].expected_path == "/foo/bar"
        assert diagnostics[0].actual_path == "/wrong/path"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_no_file_path_skips_validation(self):
        source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
        diagnostics = _parse_transform_validate(source, file_path=None)
        assert len(diagnostics) == 0

    def test_nested_path_matches(self):
        source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
        diagnostics = _parse_transform_validate(source, file_path="a/b/c")
        assert len(diagnostics) == 0


class TestUniverseWithoutAuthority:
    def test_standard_without_authority_ok(self):
        source = "define the potential position<standard:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.ReservedUniverseNameDiagnostic)

    def test_non_standard_without_authority_error(self):
        source = "define the potential position<my_universe:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.UniverseWithoutAuthorityDiagnostic)
        assert diagnostics[0].universe_name == "my_universe"
        _check_diagnostic_format(diagnostics[0], source, 1, 31)

    def test_with_authority_ok(self):
        source = "define the potential position<my.domain.com:my_universe:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0

    def test_case_insensitive_standard(self):
        source = "define the potential position<STANDARD:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 2
        assert isinstance(diagnostics[0], validator.ReservedUniverseNameDiagnostic)
        assert isinstance(diagnostics[1], validator.UniverseNameUppercaseDiagnostic)
        assert diagnostics[1].universe_name == "STANDARD"


class TestDuplicateDefinitions:
    def test_no_duplicates_ok(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/first>.\n"
            "define the potential position<my.domain.com:my_lib:/second>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0

    def test_duplicate_position_error(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.DuplicateDefinitionDiagnostic)
        assert diagnostics[0].definition_type == "position"
        assert diagnostics[0].path == "/same"
        assert diagnostics[0].first_definition_line == 1
        _check_diagnostic_format(diagnostics[0], source, 2, 1)

    def test_duplicate_action_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/same>.\n"
            "define the potential action<my.domain.com:my_lib:/same>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.DuplicateDefinitionDiagnostic)
        assert diagnostics[0].definition_type == "action"
        assert diagnostics[0].path == "/same"
        assert diagnostics[0].first_definition_line == 1
        _check_diagnostic_format(diagnostics[0], source, 2, 1)

    def test_same_path_different_types_ok(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential action<my.domain.com:my_lib:/same>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0

    def test_three_duplicates_two_errors(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
        )
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 2
        assert isinstance(diagnostics[0], validator.DuplicateDefinitionDiagnostic)
        assert isinstance(diagnostics[1], validator.DuplicateDefinitionDiagnostic)
        assert diagnostics[0].first_definition_line == 1
        assert diagnostics[1].first_definition_line == 1


class TestUniverseNameUppercase:
    def test_lowercase_universe_name_ok(self):
        source = "define the potential position<my.domain.com:my_lib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 0

    def test_uppercase_in_universe_name_error(self):
        source = "define the potential position<my.domain.com:MyLib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.UniverseNameUppercaseDiagnostic)
        assert diagnostics[0].universe_name == "MyLib"
        _check_diagnostic_format(diagnostics[0], source, 1, 45)

    def test_mixed_case_universe_name_error(self):
        source = "define the potential position<my.domain.com:myLib:/path>.\n"
        diagnostics = _parse_transform_validate(source)
        assert len(diagnostics) == 1
        assert isinstance(diagnostics[0], validator.UniverseNameUppercaseDiagnostic)
        assert diagnostics[0].universe_name == "myLib"
        _check_diagnostic_format(diagnostics[0], source, 1, 45)
