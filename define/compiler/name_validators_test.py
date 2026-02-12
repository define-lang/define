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


# TODO: Add a GLobalNamePath AST node.
def _global_name(path: list[str]) -> ast.GlobalName:
    fqun = ast.Fqun(
        multiverse=None,
        authority=None,
        universe=_universe("my_lib"),
        position=_POS,
    )
    return ast.GlobalName(fqun=fqun, path=path, position=_POS)


def _local_def(name: str) -> ast.LocalPositionDefinition:
    return ast.LocalPositionDefinition(
        local_name=ast.LocalName(name=name, position=_POS),
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


class TestGlobalNamePath:
    def test_valid(self):
        result = name_validators.validate_global_name_path(_global_name(["valid_path"]))
        assert not result

    def test_hyphen(self):
        result = name_validators.validate_global_name_path(_global_name(["bad-name"]))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[0].segment == "bad-name"
        assert result[0].position.line == 1
        assert result[0].position.column == 24

    def test_digit_start(self):
        result = name_validators.validate_global_name_path(_global_name(["2bad"]))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[0].segment == "2bad"
        assert result[0].position.line == 1
        assert result[0].position.column == 21

    def test_uppercase(self):
        result = name_validators.validate_global_name_path(_global_name(["BadName"]))
        assert len(result) == 1
        assert isinstance(result[0], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[0].segment == "BadName"
        assert result[0].position.line == 1
        assert result[0].position.column == 21

    def test_multiple_invalid_segments(self):
        result = name_validators.validate_global_name_path(
            _global_name(["Bad", "2bad"])
        )
        assert len(result) == 2
        assert isinstance(result[0], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[0].segment == "Bad"
        assert result[0].position.column == 21
        assert isinstance(result[1], diagnostics.InvalidGlobalNamePathDiagnostic)
        assert result[1].segment == "2bad"
        assert result[1].position.column == 25


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
