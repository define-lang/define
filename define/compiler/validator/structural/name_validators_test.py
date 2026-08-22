# pyright: reportUnusedCallResult=false
"""Tests for name format validators."""

from __future__ import annotations

from define.compiler import ast, diagnostics
from define.compiler.validator.structural import name_validators

_LOC = ast.SourceLocation(line=1, column=10, end_line=1, end_column=20)


def _multiverse(name: str) -> ast.Multiverse:
    return ast.Multiverse(name=name, location=_LOC)


def _authority(name: str) -> ast.Authority:
    return ast.Authority(name=name, location=_LOC)


def _universe(name: str) -> ast.Universe:
    return ast.Universe(name=name, location=_LOC)


def _global_path_name(name: str) -> ast.GlobalPathName:
    return ast.GlobalPathName(name=name, location=_LOC)


def _local_name(name: str) -> ast.LocalNameContent:
    return ast.LocalNameContent(name=name, location=_LOC)


def _fqun(
    universe: str,
    authority: ast.Authority | None = None,
    multiverse: ast.Multiverse | None = None,
) -> ast.Fqun:
    return ast.Fqun(
        multiverse=multiverse,
        authority=authority,
        universe=_universe(universe),
        location=_LOC,
    )


def _global_name(
    fqun: ast.Fqun,
    path_name: str,
) -> ast.DefinitionGlobalNameContent:
    return ast.DefinitionGlobalNameContent(
        fqun=fqun,
        path=_global_path_name(path_name),
        location=_LOC,
    )


def _validate_multiverse_name(multiverse: ast.Multiverse):
    return name_validators.validate_global_name(
        _global_name(
            _fqun(
                "my_lib",
                authority=_authority("my.domain.com"),
                multiverse=multiverse,
            ),
            "/valid_path",
        )
    )


def _validate_authority(
    authority: ast.Authority, multiverse: ast.Multiverse | None = None
):
    return name_validators.validate_global_name(
        _global_name(
            _fqun("my_lib", authority=authority, multiverse=multiverse),
            "/valid_path",
        )
    )


def _validate_authority_format(authority: ast.Authority):
    return _validate_authority(authority, _multiverse("custom"))


def _validate_universe_name(universe: ast.Universe):
    return name_validators.validate_global_name(
        ast.DefinitionGlobalNameContent(
            fqun=ast.Fqun(
                multiverse=None,
                authority=_authority("my.domain.com"),
                universe=universe,
                location=_LOC,
            ),
            path=_global_path_name("/valid_path"),
            location=_LOC,
        )
    )


def _validate_global_name_path(path: ast.GlobalPathName):
    return name_validators.validate_global_name(
        ast.DefinitionGlobalNameContent(
            fqun=_fqun("my_lib", authority=_authority("my.domain.com")),
            path=path,
            location=_LOC,
        )
    )


def _validate_fqun(fqun: ast.Fqun):
    return name_validators.validate_global_name(_global_name(fqun, "/valid_path"))


class TestMultiverseNameFormat:
    def test_valid(self):
        result = _validate_multiverse_name(_multiverse("my_mv"))
        assert not result

    def test_leading_underscore(self):
        result = _validate_multiverse_name(_multiverse("_mv"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert result[0].multiverse_name == "_mv"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_trailing_underscore(self):
        result = _validate_multiverse_name(_multiverse("mv_"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert result[0].multiverse_name == "mv_"
        assert result[0].location.line == 1
        assert result[0].location.column == 12

    def test_single_char(self):
        result = _validate_multiverse_name(_multiverse("x"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.MultiverseNameTooShortDiagnostic)
        assert result[0].multiverse_name == "x"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_single_char_invalid(self):
        result = _validate_multiverse_name(_multiverse("_"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.MultiverseNameTooShortDiagnostic)
        assert result[0].location.column == 10
        assert isinstance(result[1], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert result[1].location.column == 10

    def test_uppercase(self):
        result = _validate_multiverse_name(_multiverse("Mv"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert result[0].multiverse_name == "Mv"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_non_ascii(self):
        result = _validate_multiverse_name(_multiverse("muv\u00e9"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert result[0].multiverse_name == "muv\u00e9"
        assert result[0].location.line == 1
        assert result[0].location.column == 13


class TestAuthorityDomainFormat:
    def test_valid(self):
        result = _validate_authority_format(_authority("my.domain.com"))
        assert not result

    def test_leading_hyphen(self):
        result = _validate_authority_format(_authority("-example.com"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == "-example.com"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_trailing_dot(self):
        result = _validate_authority_format(_authority("example.com."))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == "example.com."
        assert result[0].location.line == 1
        assert result[0].location.column == 21

    def test_single_char(self):
        result = _validate_authority_format(_authority("a"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainTooShortDiagnostic)
        assert result[0].domain == "a"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_two_char_domain_is_valid(self):
        result = _validate_authority_format(_authority("ab"))
        assert not result

    def test_trailing_hyphen(self):
        result = _validate_authority_format(_authority("example.com-"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == "example.com-"
        assert result[0].location.line == 1
        assert result[0].location.column == 21

    def test_leading_dot(self):
        result = _validate_authority_format(_authority(".example.com"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == ".example.com"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_single_char_invalid(self):
        result = _validate_authority_format(_authority("-"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.AuthorityDomainTooShortDiagnostic)
        assert result[0].location.column == 10
        assert isinstance(result[1], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[1].location.column == 10

    def test_uppercase(self):
        result = _validate_authority_format(_authority("Something.Com"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == "Something.Com"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_non_ascii(self):
        result = _validate_authority_format(_authority("ex\u00e4mple.com"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert result[0].domain == "ex\u00e4mple.com"
        assert result[0].location.line == 1
        assert result[0].location.column == 12


class TestAuthorityPathFormat:
    def test_valid(self):
        result = _validate_authority_format(_authority("example.org/org/repo"))
        assert not result

    def test_leading_dot(self):
        result = _validate_authority_format(_authority("example.org/.hidden"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == ".hidden"
        assert result[0].location.line == 1
        assert result[0].location.column == 22

    def test_uppercase(self):
        result = _validate_authority_format(_authority("example.org/Bad"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].location.line == 1
        assert result[0].location.column == 22

    def test_multiple_invalid_segments(self):
        result = _validate_authority_format(_authority("example.org/Bad/.hidden"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].location.column == 22
        assert isinstance(result[1], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[1].segment == ".hidden"
        assert result[1].location.column == 26

    def test_empty_segment(self):
        result = _validate_authority_format(_authority("example.org//repo"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityPathEmptySegmentDiagnostic)
        assert result[0].authority == "example.org//repo"
        assert result[0].location.column == 21

    def test_leading_slash_splits_into_empty_domain(self):
        result = _validate_authority_format(_authority("/repo"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.AuthorityDomainTooShortDiagnostic)
        assert result[0].domain == ""


class TestUniverseNameFormat:
    def test_valid(self):
        result = _validate_universe_name(_universe("my_lib"))
        assert not result

    def test_leading_underscore(self):
        result = _validate_universe_name(_universe("_my_lib"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseNameInvalidCharDiagnostic)
        assert result[0].universe_name == "_my_lib"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_trailing_underscore(self):
        result = _validate_universe_name(_universe("my_lib_"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseNameInvalidCharDiagnostic)
        assert result[0].universe_name == "my_lib_"
        assert result[0].location.line == 1
        assert result[0].location.column == 16

    def test_single_char(self):
        result = _validate_universe_name(_universe("x"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseNameTooShortDiagnostic)
        assert result[0].universe_name == "x"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_two_char_universe_is_valid(self):
        result = _validate_universe_name(_universe("ab"))
        assert not result

    def test_single_char_invalid(self):
        result = _validate_universe_name(_universe("_"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.UniverseNameTooShortDiagnostic)
        assert result[0].location.column == 10
        assert isinstance(result[1], diagnostics.UniverseNameInvalidCharDiagnostic)
        assert result[1].location.column == 10

    def test_uppercase(self):
        result = _validate_universe_name(_universe("MyLib"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseNameInvalidCharDiagnostic)
        assert result[0].universe_name == "MyLib"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_non_ascii(self):
        result = _validate_universe_name(_universe("m\u00fclib"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseNameInvalidCharDiagnostic)
        assert result[0].universe_name == "m\u00fclib"
        assert result[0].location.line == 1
        assert result[0].location.column == 11


class TestGlobalNamePath:
    def test_valid_multiple_segments(self):
        result = _validate_global_name_path(_global_path_name("/some/valid_path"))
        assert not result

    def test_multiple_invalid_segments(self):
        result = _validate_global_name_path(_global_path_name("/Bad/2bad"))
        assert len(result) == 2
        assert isinstance(
            result[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )
        assert result[0].segment == "Bad"
        assert result[0].location.column == 11
        assert isinstance(
            result[1], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )
        assert result[1].segment == "2bad"
        assert result[1].location.column == 15

    def test_missing_leading_slash(self):
        result = _validate_global_name_path(_global_path_name("invalid/path"))
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic
        )
        assert result[0].path == "invalid/path"
        assert result[0].location.column == 10

    def test_bare_slash(self):
        result = _validate_global_name_path(_global_path_name("/"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
        assert result[0].path == "/"
        assert result[0].location.column == 10

    def test_trailing_slash(self):
        result = _validate_global_name_path(_global_path_name("/invalid/path/"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.GlobalNamePathTrailingSlashDiagnostic)
        assert result[0].path == "/invalid/path/"
        assert result[0].location.column == 23

    def test_empty_segment(self):
        result = _validate_global_name_path(_global_path_name("/invalid//path"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.GlobalNamePathEmptySegmentDiagnostic)
        assert result[0].path == "/invalid//path"
        assert result[0].location.column == 18

    def test_segment_starting_with_dot(self):
        result = _validate_global_name_path(_global_path_name("/.hidden/path"))
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )
        assert result[0].segment == ".hidden"
        assert result[0].location.column == 11

    def test_all_diagnostic_types(self):
        result = _validate_global_name_path(_global_path_name("Bad//2bad/"))
        assert len(result) == 4
        assert (
            sum(
                isinstance(d, diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic)
                for d in result
            )
            == 1
        )
        assert (
            sum(
                isinstance(d, diagnostics.GlobalNamePathTrailingSlashDiagnostic)
                for d in result
            )
            == 1
        )
        assert (
            sum(
                isinstance(d, diagnostics.GlobalNamePathEmptySegmentDiagnostic)
                for d in result
            )
            == 1
        )
        assert (
            sum(
                isinstance(d, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
                for d in result
            )
            == 1
        )


class TestMultiverseNameReserved:
    def test_reserved_programming_language(self):
        result = _validate_multiverse_name(_multiverse("python"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "python"
        assert result[0].location.column == 10

    def test_reserved_package_repository(self):
        result = _validate_multiverse_name(_multiverse("npm"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "npm"

    def test_reserved_common_word(self):
        result = _validate_multiverse_name(_multiverse("about"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "about"

    def test_mv_is_allowed(self):
        result = _validate_multiverse_name(_multiverse("mv"))
        assert not result

    def test_non_reserved(self):
        result = _validate_multiverse_name(_multiverse("my_custom_mv"))
        assert not result

    def test_case_insensitive(self):
        result = _validate_multiverse_name(_multiverse("Python"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert isinstance(result[1], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[1].reserved_name == "Python"


class TestAuthorityReserved:
    def test_reserved_domain(self):
        result = _validate_authority(_authority("example.com"), None)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert result[0].reserved_name == "example.com"
        assert result[0].location.column == 10

    def test_reserved_common_word_domain(self):
        result = _validate_authority(_authority("standard"), None)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert result[0].reserved_name == "standard"

    def test_dotless_domain_in_local_multiverse(self):
        result = _validate_authority(_authority("localhost"), None)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.DotlessAuthorityDomainDiagnostic)
        assert result[0].location.column == 10

    def test_dotless_domain_in_mv_multiverse(self):
        result = _validate_authority(_authority("myhost"), _multiverse("mv"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.DotlessAuthorityDomainDiagnostic)

    def test_dotless_domain_in_custom_multiverse(self):
        result = _validate_authority(_authority("myhost"), _multiverse("custom"))
        assert not result

    def test_dotted_domain_ok(self):
        result = _validate_authority(_authority("my.domain.com"), None)
        assert not result

    def test_case_insensitive(self):
        result = _validate_authority(_authority("Example.Com"), None)
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.AuthorityDomainInvalidCharDiagnostic)
        assert isinstance(result[1], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert result[1].reserved_name == "Example.Com"


class TestUniverseNameReserved:
    def test_reserved_name(self):
        result = _validate_universe_name(_universe("standard"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)
        assert result[0].reserved_name == "standard"
        assert result[0].location.column == 10

    def test_reserved_common_word(self):
        result = _validate_universe_name(_universe("about"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)

    def test_non_reserved_lowercase(self):
        result = _validate_universe_name(_universe("my_library"))
        assert not result


class TestLocalNameFormat:
    def test_valid(self):
        result = name_validators.validate_local_name_format(_local_name("my_pos"))
        assert not result

    def test_valid_leading_underscore(self):
        result = name_validators.validate_local_name_format(_local_name("_private"))
        assert not result

    def test_valid_with_digits(self):
        result = name_validators.validate_local_name_format(_local_name("pos_1"))
        assert not result

    def test_valid_single_char(self):
        result = name_validators.validate_local_name_format(_local_name("x"))
        assert not result

    def test_valid_single_underscore(self):
        result = name_validators.validate_local_name_format(_local_name("_"))
        assert not result

    def test_hyphen(self):
        result = name_validators.validate_local_name_format(_local_name("my-pos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "my-pos"
        assert result[0].location.line == 1
        assert result[0].location.column == 12

    def test_digit_start(self):
        result = name_validators.validate_local_name_format(_local_name("2bad"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "2bad"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_uppercase(self):
        result = name_validators.validate_local_name_format(_local_name("MyPos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "MyPos"
        assert result[0].location.line == 1
        assert result[0].location.column == 10

    def test_slash(self):
        result = name_validators.validate_local_name_format(_local_name("my/pos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "my/pos"
        assert result[0].location.line == 1
        assert result[0].location.column == 12


class TestValidateFqun:
    def test_valid_with_authority(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        result = _validate_fqun(fqun)
        assert not result

    def test_standard_without_authority(self):
        fqun = _fqun("standard")
        result = _validate_fqun(fqun)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)

    def test_universe_without_authority_not_standard(self):
        fqun = _fqun("my_lib")
        result = _validate_fqun(fqun)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseWithoutAuthorityDiagnostic)
        assert result[0].universe_name == "my_lib"
        assert result[0].location.column == 10

    def test_invalid_multiverse_and_reserved_universe(self):
        fqun = _fqun(
            "standard",
            authority=_authority("example.com"),
            multiverse=_multiverse("_"),
        )
        result = _validate_fqun(fqun)
        assert len(result) == 4
        assert isinstance(result[0], diagnostics.MultiverseNameTooShortDiagnostic)
        assert isinstance(result[1], diagnostics.MultiverseNameInvalidCharDiagnostic)
        assert isinstance(result[2], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert isinstance(result[3], diagnostics.ReservedUniverseNameDiagnostic)

    def test_reserved_authority(self):
        fqun = _fqun("my_lib", authority=_authority("example.com"))
        result = _validate_fqun(fqun)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityDomainDiagnostic)

    def test_custom_multiverse_dotless_authority_allowed(self):
        fqun = _fqun(
            "my_lib",
            authority=_authority("myhost"),
            multiverse=_multiverse("custom"),
        )
        result = _validate_fqun(fqun)
        assert not result

    def test_collects_all_diagnostics(self):
        fqun = _fqun(
            "standard",
            authority=_authority("example.com"),
            multiverse=_multiverse("python"),
        )
        result = _validate_fqun(fqun)
        assert len(result) == 3
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert isinstance(result[1], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert isinstance(result[2], diagnostics.ReservedUniverseNameDiagnostic)


class TestValidateGlobalName:
    def test_valid(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = _global_name(fqun, "/some/path")
        result = name_validators.validate_global_name(name)
        assert not result

    def test_fqun_errors_collected(self):
        fqun = _fqun("my_lib")
        name = _global_name(fqun, "/valid_path")
        result = name_validators.validate_global_name(name)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseWithoutAuthorityDiagnostic)

    def test_path_errors_collected(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = _global_name(fqun, "/Bad")
        result = name_validators.validate_global_name(name)
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )

    def test_fqun_and_path_errors_combined(self):
        fqun = _fqun("my_lib")
        name = _global_name(fqun, "/Bad")
        result = name_validators.validate_global_name(name)
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.UniverseWithoutAuthorityDiagnostic)
        assert isinstance(
            result[1], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )

    def test_reference_without_fqun_skips_fqun_validation(self):
        name = ast.ReferenceGlobalNameContent(
            fqun=None,
            path=_global_path_name("/valid_path"),
            location=_LOC,
        )
        result = name_validators.validate_global_name(name)
        assert not result

    def test_reference_same_fqun_must_use_short_form(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.ReferenceGlobalNameContent(
            fqun=fqun,
            path=_global_path_name("/valid_path"),
            location=_LOC,
        )
        result = name_validators.validate_global_name(name, must_use_short_form=fqun)
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
        )
        assert result[0].fqun == "my.domain.com:my_lib"
        assert result[0].location.column == 10

    def test_reference_with_different_fqun_allows_full_form(self):
        name_fqun = _fqun("other_lib", authority=_authority("other.domain.com"))
        enclosing_fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.ReferenceGlobalNameContent(
            fqun=name_fqun,
            path=_global_path_name("/valid_path"),
            location=_LOC,
        )
        result = name_validators.validate_global_name(
            name, must_use_short_form=enclosing_fqun
        )
        assert not result

    def test_reference_short_form_allowed_when_required(self):
        enclosing_fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.ReferenceGlobalNameContent(
            fqun=None,
            path=_global_path_name("/valid_path"),
            location=_LOC,
        )
        result = name_validators.validate_global_name(
            name, must_use_short_form=enclosing_fqun
        )
        assert not result


def _enclosing_definition() -> ast.PositionDefinition:
    return ast.PositionDefinition(
        name=ast.DefinitionGlobalNameContent(
            fqun=_fqun("my_lib", authority=_authority("my.domain.com")),
            path=_global_path_name("/test"),
            location=_LOC,
        ),
        location=_LOC,
    )


class TestValidateTypedName:
    def test_global_reference_valid(self):
        ref = ast.GlobalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                fqun=None,
                path=_global_path_name("/other"),
                location=_LOC,
            ),
            enclosing_fqun=_fqun("my_lib", authority=_authority("my.domain.com")),
            location=_LOC,
        )
        result = name_validators.validate_typed_name(ref, _enclosing_definition())
        assert not result

    def test_global_reference_same_fqun_must_use_short_form(self):
        ref = ast.GlobalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.ReferenceGlobalNameContent(
                fqun=_fqun("my_lib", authority=_authority("my.domain.com")),
                path=_global_path_name("/other"),
                location=_LOC,
            ),
            enclosing_fqun=_fqun("my_lib", authority=_authority("my.domain.com")),
            location=_LOC,
        )
        result = name_validators.validate_typed_name(ref, _enclosing_definition())
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
        )

    def test_local_reference_valid(self):
        ref = ast.LocalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.LocalNameContent(name="my_pos", location=_LOC),
            location=_LOC,
        )
        result = name_validators.validate_typed_name(ref, _enclosing_definition())
        assert not result

    def test_local_reference_invalid_char(self):
        ref = ast.LocalTypedNameReference(
            name_type=ast.NameType.POSITION,
            name_content=ast.LocalNameContent(name="My-pos", location=_LOC),
            location=_LOC,
        )
        result = name_validators.validate_typed_name(ref, _enclosing_definition())
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
