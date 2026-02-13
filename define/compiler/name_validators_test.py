# pyright: reportUnusedCallResult=false
"""Tests for name format validators."""

from define.compiler import ast, diagnostics, name_validators

_POS = ast.SourcePosition(line=1, column=10, end_line=1, end_column=20)


def _multiverse(name: str) -> ast.Multiverse:
    return ast.Multiverse(name=name, position=_POS)


def _authority(domain: str, path: list[str] | None = None) -> ast.Authority:
    return ast.Authority(domain=domain, path=path or [], position=_POS)


def _universe(name: str) -> ast.Universe:
    return ast.Universe(name=name, position=_POS)


def _path_segment(name: str) -> ast.GlobalPathNameSegment:
    col = _POS.end_column + 1  # skip '/' separator
    return ast.GlobalPathNameSegment(
        name=name,
        position=ast.SourcePosition(
            line=_POS.line,
            column=col,
            end_line=_POS.end_line,
            end_column=col + len(name),
        ),
    )


def _global_path_name(segments: list[str]) -> ast.GlobalPathName:
    col = _POS.end_column
    path_segments: list[ast.GlobalPathNameSegment] = []
    for seg in segments:
        col += 1  # skip '/' separator
        path_segments.append(
            ast.GlobalPathNameSegment(
                name=seg,
                position=ast.SourcePosition(
                    line=_POS.line,
                    column=col,
                    end_line=_POS.end_line,
                    end_column=col + len(seg),
                ),
            )
        )
        col += len(seg)
    return ast.GlobalPathName(segments=path_segments, position=_POS)


def _local_def(name: str) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalName(name=name, position=_POS),
        position=_POS,
    )


def _fqun(
    universe: str,
    authority: ast.Authority | None = None,
    multiverse: ast.Multiverse | None = None,
) -> ast.Fqun:
    return ast.Fqun(
        multiverse=multiverse,
        authority=authority,
        universe=_universe(universe),
        position=_POS,
    )


def _global_name(
    fqun: ast.Fqun,
    path_segments: list[str],
) -> ast.GlobalNameDefinition:
    return ast.GlobalNameDefinition(
        fqun=fqun,
        path=_global_path_name(path_segments),
        position=_POS,
    )


class TestMultiverseNameFormat:
    def test_valid(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("my_mv"))
        assert not result

    def test_leading_underscore(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("_mv"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[0].multiverse_name == "_mv"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_trailing_underscore(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("mv_"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[0].multiverse_name == "mv_"
        assert result[0].position.line == 1
        assert result[0].position.column == 12

    def test_single_char(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("x"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[0].multiverse_name == "x"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_single_char_invalid(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("_"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[0].position.column == 10
        assert isinstance(result[1], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[1].position.column == 10

    def test_uppercase(self):
        result = name_validators.validate_multiverse_name_format(_multiverse("Mv"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidMultiverseNameDiagnostic)
        assert result[0].multiverse_name == "Mv"
        assert result[0].position.line == 1
        assert result[0].position.column == 10


class TestAuthorityDomainFormat:
    def test_valid(self):
        result = name_validators.validate_authority_domain_format(
            _authority("my.domain.com")
        )
        assert not result

    def test_leading_hyphen(self):
        result = name_validators.validate_authority_domain_format(
            _authority("-example.com")
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[0].domain == "-example.com"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_trailing_dot(self):
        result = name_validators.validate_authority_domain_format(
            _authority("example.com.")
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[0].domain == "example.com."
        assert result[0].position.line == 1
        assert result[0].position.column == 21

    def test_single_char(self):
        result = name_validators.validate_authority_domain_format(_authority("a"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[0].domain == "a"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_single_char_invalid(self):
        result = name_validators.validate_authority_domain_format(_authority("-"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[0].position.column == 10
        assert isinstance(result[1], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[1].position.column == 10

    def test_uppercase(self):
        result = name_validators.validate_authority_domain_format(
            _authority("Example.Com")
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityDomainDiagnostic)
        assert result[0].domain == "Example.Com"
        assert result[0].position.line == 1
        assert result[0].position.column == 10


class TestAuthorityPathFormat:
    def test_valid(self):
        result = name_validators.validate_authority_path_format(
            _authority("example.com", ["org", "repo"])
        )
        assert not result

    def test_leading_dot(self):
        result = name_validators.validate_authority_path_format(
            _authority("example.com", [".hidden"])
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == ".hidden"
        assert result[0].position.line == 1
        assert result[0].position.column == 22

    def test_uppercase(self):
        result = name_validators.validate_authority_path_format(
            _authority("example.com", ["Bad"])
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].position.line == 1
        assert result[0].position.column == 22

    def test_multiple_invalid_segments(self):
        result = name_validators.validate_authority_path_format(
            _authority("example.com", ["Bad", ".hidden"])
        )
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].position.column == 22
        assert isinstance(result[1], diagnostics.InvalidAuthorityPathSegmentDiagnostic)
        assert result[1].segment == ".hidden"
        assert result[1].position.column == 26


class TestUniverseNameFormat:
    def test_valid(self):
        result = name_validators.validate_universe_name_format(_universe("my_lib"))
        assert not result

    def test_leading_underscore(self):
        result = name_validators.validate_universe_name_format(_universe("_my_lib"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[0].universe_name == "_my_lib"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_trailing_underscore(self):
        result = name_validators.validate_universe_name_format(_universe("my_lib_"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[0].universe_name == "my_lib_"
        assert result[0].position.line == 1
        assert result[0].position.column == 16

    def test_single_char(self):
        result = name_validators.validate_universe_name_format(_universe("x"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[0].universe_name == "x"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_single_char_invalid(self):
        result = name_validators.validate_universe_name_format(_universe("_"))
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[0].position.column == 10
        assert isinstance(result[1], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[1].position.column == 10

    def test_uppercase(self):
        result = name_validators.validate_universe_name_format(_universe("MyLib"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidUniverseNameFormatDiagnostic)
        assert result[0].universe_name == "MyLib"
        assert result[0].position.line == 1
        assert result[0].position.column == 10


class TestGlobalNamePathSegment:
    def test_valid(self):
        result = name_validators.validate_global_name_path_segment(
            _path_segment("valid_path")
        )
        assert result is None

    def test_hyphen(self):
        result = name_validators.validate_global_name_path_segment(
            _path_segment("bad-name")
        )
        assert result is not None
        assert isinstance(result, diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result.segment == "bad-name"
        assert result.position.line == 1
        assert result.position.column == 24

    def test_digit_start(self):
        result = name_validators.validate_global_name_path_segment(
            _path_segment("2bad")
        )
        assert result is not None
        assert isinstance(result, diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result.segment == "2bad"
        assert result.position.line == 1
        assert result.position.column == 21

    def test_uppercase(self):
        result = name_validators.validate_global_name_path_segment(
            _path_segment("BadName")
        )
        assert result is not None
        assert isinstance(result, diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result.segment == "BadName"
        assert result.position.line == 1
        assert result.position.column == 21


class TestGlobalNamePath:
    def test_valid_multiple_segments(self):
        result = name_validators.validate_global_name_path(
            _global_path_name(["some", "valid_path"])
        )
        assert not result

    def test_multiple_invalid_segments(self):
        result = name_validators.validate_global_name_path(
            _global_path_name(["Bad", "2bad"])
        )
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].position.column == 21
        assert isinstance(result[1], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[1].segment == "2bad"
        assert result[1].position.column == 25


class TestMultiverseNameReserved:
    def test_reserved_programming_language(self):
        result = name_validators.validate_multiverse_name_reserved(
            _multiverse("python")
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "python"

    def test_reserved_package_repository(self):
        result = name_validators.validate_multiverse_name_reserved(_multiverse("npm"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "npm"

    def test_reserved_common_word(self):
        result = name_validators.validate_multiverse_name_reserved(_multiverse("about"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedMultiverseNameDiagnostic)
        assert result[0].reserved_name == "about"

    def test_mv_is_allowed(self):
        result = name_validators.validate_multiverse_name_reserved(_multiverse("mv"))
        assert not result

    def test_non_reserved(self):
        result = name_validators.validate_multiverse_name_reserved(
            _multiverse("my_custom_mv")
        )
        assert not result

    def test_case_insensitive(self):
        result = name_validators.validate_multiverse_name_reserved(
            _multiverse("Python")
        )
        assert len(result) == 1
        assert result[0].reserved_name == "Python"


class TestAuthorityReserved:
    def test_reserved_domain(self):
        result = name_validators.validate_authority_reserved(
            _authority("example.com"), None
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityNameDiagnostic)
        assert result[0].reserved_name == "example.com"

    def test_reserved_common_word_domain(self):
        result = name_validators.validate_authority_reserved(
            _authority("standard"), None
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityNameDiagnostic)
        assert result[0].reserved_name == "standard"

    def test_dotless_domain_in_local_multiverse(self):
        result = name_validators.validate_authority_reserved(
            _authority("localhost"), None
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityNameDiagnostic)

    def test_dotless_domain_in_mv_multiverse(self):
        result = name_validators.validate_authority_reserved(
            _authority("myhost"), _multiverse("mv")
        )
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedAuthorityNameDiagnostic)

    def test_dotless_domain_in_custom_multiverse(self):
        result = name_validators.validate_authority_reserved(
            _authority("myhost"), _multiverse("custom")
        )
        assert not result

    def test_dotted_domain_ok(self):
        result = name_validators.validate_authority_reserved(
            _authority("my.domain.com"), None
        )
        assert not result

    def test_case_insensitive(self):
        result = name_validators.validate_authority_reserved(
            _authority("Example.Com"), None
        )
        assert len(result) == 1
        assert result[0].reserved_name == "Example.Com"


class TestUniverseNameReserved:
    def test_reserved_name(self):
        result = name_validators.validate_universe_name_reserved(_universe("standard"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)
        assert result[0].reserved_name == "standard"

    def test_reserved_common_word(self):
        result = name_validators.validate_universe_name_reserved(_universe("about"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)

    def test_non_reserved_lowercase(self):
        result = name_validators.validate_universe_name_reserved(
            _universe("my_library")
        )
        assert not result


class TestLocalNameFormat:
    def test_valid(self):
        result = name_validators.validate_local_name_format(_local_def("my_pos"))
        assert not result

    def test_hyphen(self):
        result = name_validators.validate_local_name_format(_local_def("my-pos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "my-pos"
        assert result[0].position.line == 1
        assert result[0].position.column == 12

    def test_digit_start(self):
        result = name_validators.validate_local_name_format(_local_def("2bad"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "2bad"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_uppercase(self):
        result = name_validators.validate_local_name_format(_local_def("MyPos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "MyPos"
        assert result[0].position.line == 1
        assert result[0].position.column == 10

    def test_slash(self):
        result = name_validators.validate_local_name_format(_local_def("my/pos"))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidLocalNameFormatDiagnostic)
        assert result[0].local_name == "my/pos"
        assert result[0].position.line == 1
        assert result[0].position.column == 12


class TestValidateFqun:
    def test_valid_with_authority(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        result = name_validators.validate_fqun(fqun)
        assert not result

    def test_standard_without_authority(self):
        fqun = _fqun("standard")
        result = name_validators.validate_fqun(fqun)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.ReservedUniverseNameDiagnostic)

    def test_universe_without_authority_not_standard(self):
        fqun = _fqun("my_lib")
        result = name_validators.validate_fqun(fqun)
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.UniverseWithoutAuthorityDiagnostic)
        assert result[0].universe_name == "my_lib"

    def test_invalid_multiverse_and_reserved_universe(self):
        fqun = _fqun(
            "standard",
            authority=_authority("example.com"),
            multiverse=_multiverse("_"),
        )
        result = name_validators.validate_fqun(fqun)
        mv_diags = [
            d
            for d in result
            if isinstance(d, diagnostics.InvalidMultiverseNameDiagnostic)
        ]
        assert len(mv_diags) >= 1

    def test_reserved_authority(self):
        fqun = _fqun("my_lib", authority=_authority("example.com"))
        result = name_validators.validate_fqun(fqun)
        reserved = [
            d
            for d in result
            if isinstance(d, diagnostics.ReservedAuthorityNameDiagnostic)
        ]
        assert len(reserved) == 1

    def test_collects_all_diagnostics(self):
        fqun = _fqun(
            "standard",
            authority=_authority("example.com"),
            multiverse=_multiverse("python"),
        )
        result = name_validators.validate_fqun(fqun)
        reserved_mv = [
            d
            for d in result
            if isinstance(d, diagnostics.ReservedMultiverseNameDiagnostic)
        ]
        reserved_auth = [
            d
            for d in result
            if isinstance(d, diagnostics.ReservedAuthorityNameDiagnostic)
        ]
        assert len(reserved_mv) == 1
        assert len(reserved_auth) == 1


class TestValidateGlobalName:
    def test_valid(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = _global_name(fqun, ["some", "path"])
        result = name_validators.validate_global_name(name)
        assert not result

    def test_fqun_errors_collected(self):
        fqun = _fqun("my_lib")
        name = _global_name(fqun, ["valid_path"])
        result = name_validators.validate_global_name(name)
        assert any(
            isinstance(d, diagnostics.UniverseWithoutAuthorityDiagnostic)
            for d in result
        )

    def test_path_errors_collected(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = _global_name(fqun, ["Bad"])
        result = name_validators.validate_global_name(name)
        assert any(
            isinstance(d, diagnostics.InvalidGlobalNamePathDiagnostic) for d in result
        )

    def test_fqun_and_path_errors_combined(self):
        fqun = _fqun("my_lib")
        name = _global_name(fqun, ["Bad"])
        result = name_validators.validate_global_name(name)
        fqun_errors = [
            d
            for d in result
            if isinstance(d, diagnostics.UniverseWithoutAuthorityDiagnostic)
        ]
        path_errors = [
            d
            for d in result
            if isinstance(d, diagnostics.InvalidGlobalNamePathDiagnostic)
        ]
        assert len(fqun_errors) == 1
        assert len(path_errors) == 1

    def test_reference_without_fqun_skips_fqun_validation(self):
        name = ast.GlobalNameReference(
            fqun=None,
            path=_global_path_name(["valid_path"]),
            position=_POS,
        )
        result = name_validators.validate_global_name(name)
        assert not result

    def test_reference_same_fqun_must_use_short_form(self):
        fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.GlobalNameReference(
            fqun=fqun,
            path=_global_path_name(["valid_path"]),
            position=_POS,
        )
        result = name_validators.validate_global_name(name, must_use_short_form=fqun)
        assert len(result) == 1
        assert isinstance(
            result[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
        )
        assert result[0].fqun == "my.domain.com:my_lib"

    def test_reference_with_different_fqun_allows_full_form(self):
        name_fqun = _fqun("other_lib", authority=_authority("other.domain.com"))
        enclosing_fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.GlobalNameReference(
            fqun=name_fqun,
            path=_global_path_name(["valid_path"]),
            position=_POS,
        )
        result = name_validators.validate_global_name(
            name, must_use_short_form=enclosing_fqun
        )
        assert not result

    def test_reference_short_form_allowed_when_required(self):
        enclosing_fqun = _fqun("my_lib", authority=_authority("my.domain.com"))
        name = ast.GlobalNameReference(
            fqun=None,
            path=_global_path_name(["valid_path"]),
            position=_POS,
        )
        result = name_validators.validate_global_name(
            name, must_use_short_form=enclosing_fqun
        )
        assert not result
