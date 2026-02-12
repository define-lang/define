"""Tests for the Define language validator."""

from define.compiler import diagnostics, parser, validator
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()
_transformer = DefineTransformer()


def _parse_transform_validate(
    source: str,
    file_path: str | None = None,
    expected_universe_name: str | None = None,
) -> list[diagnostics.Diagnostic]:
    tree = _parser.parse(source)
    program = _transformer.transform(tree)
    return validator.Validator(program, source).validate(
        file_path=file_path, expected_universe_name=expected_universe_name
    )


def _check_diagnostic_format(
    diagnostic: diagnostics.Diagnostic,
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


class TestReservedNamePositions:
    def test_reserved_universe_name_position(self):
        source = "define the potential position<standard:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_reserved_universe_name_with_authority_position(self):
        source = "define the potential position<example.com:example:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.ReservedAuthorityNameDiagnostic)
        assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
        _check_diagnostic_format(diags[1], source, 1, 43)

    def test_reserved_authority_position(self):
        source = "define the potential position<example.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedAuthorityNameDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_reserved_authority_with_multiverse_position(self):
        source = "define the potential position<mv:example.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedAuthorityNameDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 34)

    def test_dotless_authority_position(self):
        source = "define the potential position<localhost:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedAuthorityNameDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_reserved_multiverse_position(self):
        source = "define the potential position<python:example.org:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedMultiverseNameDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 31)


class TestDiagnosticCollection:
    def test_multiple_diagnostics_collected(self):
        source = (
            "define the potential position<standard:/first>.\n"
            "define the potential position<standard:/second>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        _check_diagnostic_format(diags[0], source, 1, 31)
        _check_diagnostic_format(diags[1], source, 2, 31)

    def test_diagnostics_in_source_order(self):
        source = (
            "define the potential position<standard:/first>.\n"
            "define the potential position<standard:/second>.\n"
        )
        diags = _parse_transform_validate(source)
        assert diags[0].position.line == 1
        assert diags[1].position.line == 2


class TestPathMismatch:
    def test_path_matches_file_no_error(self):
        source = "define the potential position<my.domain.com:my_lib:/foo/bar>.\n"
        diags = _parse_transform_validate(source, file_path="foo/bar")
        assert len(diags) == 0

    def test_path_mismatch_error(self):
        source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
        diags = _parse_transform_validate(source, file_path="foo/bar")
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
        assert diags[0].expected_path == "/foo/bar"
        assert diags[0].actual_path == "/wrong/path"
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_no_file_path_skips_validation(self):
        source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
        diags = _parse_transform_validate(source, file_path=None)
        assert len(diags) == 0

    def test_nested_path_matches(self):
        source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
        diags = _parse_transform_validate(source, file_path="a/b/c")
        assert len(diags) == 0


class TestUniverseWithoutAuthority:
    def test_standard_without_authority_ok(self):
        source = "define the potential position<standard:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)

    def test_non_standard_without_authority_error(self):
        source = "define the potential position<my_universe:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.UniverseWithoutAuthorityDiagnostic)
        assert diags[0].universe_name == "my_universe"
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_with_authority_ok(self):
        source = "define the potential position<my.domain.com:my_universe:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_case_insensitive_standard(self):
        source = "define the potential position<STANDARD:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)


class TestDuplicateDefinitions:
    def test_no_duplicates_ok(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/first>.\n"
            "define the potential position<my.domain.com:my_lib:/second>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_duplicate_position_error(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
        assert diags[0].definition_type == "position"
        assert diags[0].path == "/same"
        assert diags[0].first_definition_line == 1
        _check_diagnostic_format(diags[0], source, 2, 1)

    def test_duplicate_action_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/same>.\n"
            "define the potential action<my.domain.com:my_lib:/same>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
        assert diags[0].definition_type == "action"
        assert diags[0].path == "/same"
        assert diags[0].first_definition_line == 1
        _check_diagnostic_format(diags[0], source, 2, 1)

    def test_same_path_different_types_ok(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential action<my.domain.com:my_lib:/same>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_three_duplicates_two_errors(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
            "define the potential position<my.domain.com:my_lib:/same>.\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.DuplicateDefinitionDiagnostic)
        assert isinstance(diags[1], diagnostics.DuplicateDefinitionDiagnostic)
        assert diags[0].first_definition_line == 1
        assert diags[1].first_definition_line == 1


class TestFqunMismatch:
    def test_matching_authority_universe(self):
        source = "define the potential position<my.domain.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="my.domain.com:my_lib"
        )
        assert len(diags) == 0

    def test_mismatched_universe(self):
        source = "define the potential position<my.domain.com:wrong_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="my.domain.com:my_lib"
        )
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
        assert diags[0].expected == "my.domain.com:my_lib"
        assert diags[0].actual == "my.domain.com:wrong_lib"

    def test_mismatched_authority(self):
        source = "define the potential position<other.org:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="my.domain.com:my_lib"
        )
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
        assert diags[0].expected == "my.domain.com:my_lib"
        assert diags[0].actual == "other.org:my_lib"

    def test_mismatched_multiverse(self):
        source = "define the potential position<npm:my.domain.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="mv:my.domain.com:my_lib"
        )
        npm_diags = [
            d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)
        ]
        assert len(npm_diags) == 1
        assert npm_diags[0].expected == "mv:my.domain.com:my_lib"
        assert npm_diags[0].actual == "npm:my.domain.com:my_lib"

    def test_none_skips_check(self):
        source = "define the potential position<my.domain.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source, expected_universe_name=None)
        assert len(diags) == 0

    def test_standard_universe_matching(self):
        source = "define the potential position<standard:/path>.\n"
        diags = _parse_transform_validate(source, expected_universe_name="standard")
        fqun_diags = [
            d for d in diags if isinstance(d, diagnostics.FqunMismatchDiagnostic)
        ]
        assert len(fqun_diags) == 0

    def test_authority_with_path(self):
        source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="my.domain.com/org:my_lib"
        )
        assert len(diags) == 0

    def test_authority_with_path_mismatch(self):
        source = "define the potential position<my.domain.com/org:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="my.domain.com:my_lib"
        )
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.FqunMismatchDiagnostic)
        assert diags[0].actual == "my.domain.com/org:my_lib"

    def test_multiverse_matching(self):
        source = "define the potential position<mv:my.domain.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(
            source, expected_universe_name="mv:my.domain.com:my_lib"
        )
        assert len(diags) == 0


# Tests just the positions of name formatting errors to make sure they are
# integrated correctly into the validator. name_validators_test checks the
# actual name-formatting logic.
class TestNameFormatPositions:
    def test_multiverse_name_position(self):
        source = "define the potential position<_mv:my.domain.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        mv_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidMultiverseNameDiagnostic)
        ]
        assert len(mv_diags) == 1
        assert mv_diags[0].position.line == 1
        assert mv_diags[0].position.column == 31

    def test_authority_domain_position(self):
        source = "define the potential position<mv:-example.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        ad_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidAuthorityDomainDiagnostic)
        ]
        assert len(ad_diags) == 1
        assert ad_diags[0].position.line == 1
        assert ad_diags[0].position.column == 34

    def test_authority_path_position(self):
        source = "define the potential position<mv:example.com/.hidden:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        ap_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        ]
        assert len(ap_diags) == 1
        assert ap_diags[0].position.line == 1
        assert ap_diags[0].position.column == 46

    def test_universe_name_position(self):
        source = "define the potential position<mv:my.domain.com:_my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        un_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidUniverseNameFormatDiagnostic)
        ]
        assert len(un_diags) == 1
        assert un_diags[0].position.line == 1
        assert un_diags[0].position.column == 48

    def test_path_segment_position(self):
        source = "define the potential position<my.domain.com:my_lib:/2bad>.\n"
        diags = _parse_transform_validate(source)
        ps_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidGlobalNamePathDiagnostic)
        ]
        assert len(ps_diags) == 1
        assert ps_diags[0].position.line == 1
        assert ps_diags[0].position.column == 53

    def test_local_name_position(self):
        source = (
            "define the potential action<mv:my.domain.com:my_lib:/act> {\n"
            "define the position<my-pos>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        ln_diags = [
            d
            for d in diags
            if isinstance(d, diagnostics.InvalidLocalNameFormatDiagnostic)
        ]
        assert len(ln_diags) == 1
        assert ln_diags[0].position.line == 2
        assert ln_diags[0].position.column == 23
