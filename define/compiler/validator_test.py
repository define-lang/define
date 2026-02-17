"""Tests for the Define language validator.

Keep test assertions simple: assert on the exact diagnostics list you get
(len, isinstance, fields) rather than filtering by type.
"""

from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

import pytest

from define.compiler import diagnostics, parser, parser_exceptions, validator
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()
_transformer = DefineTransformer()
type ParseAndValidateFile = Callable[[str | bytes], validator.ValidationResult]


def _parse_transform_validate(
    source: str,
    expected_definition_path: str | None = None,
    expected_universe_name: str | None = None,
) -> list[diagnostics.Diagnostic]:
    tree = _parser.parse(source)
    program = _transformer.transform(tree)
    path = PurePosixPath(expected_definition_path) if expected_definition_path else None
    return validator.Validator().validate(
        program=program,
        expected_definition_path=path,
        expected_universe_name=expected_universe_name,
    )


@pytest.fixture
def parse_and_validate_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ParseAndValidateFile:
    def _run(source: str | bytes) -> validator.ValidationResult:
        relative_path = Path("sub/test.def")
        source_path = tmp_path / relative_path
        source_path.parent.mkdir(parents=True)
        if isinstance(source, str):
            _ = source_path.write_text(source, encoding="utf-8")
        else:
            _ = source_path.write_bytes(source)
        monkeypatch.chdir(tmp_path)
        results = validator.Validator().parse_and_validate_program(relative_path)
        assert len(results) == 1
        return results[0]

    return _run


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
    assert caret_line.index("^") == expected_column - 1


class TestParseAndValidateFile:
    def test_returns_single_file_timing_stats(
        self,
        parse_and_validate_file: ParseAndValidateFile,
    ):
        source = "define the potential position<my.domain.com:my_lib:/sub/test>.\n"
        result = parse_and_validate_file(source)

        assert result.diagnostics == []
        assert result.exception is None
        assert result.source == source
        assert result.file_path == Path("sub/test.def")

        timings = result.stats
        assert timings.overall >= 0
        assert timings.parse >= 0
        assert timings.transform is not None
        assert timings.validate is not None
        assert timings.transform >= 0
        assert timings.validate >= 0
        assert timings.parse < timings.overall
        assert timings.transform < timings.overall
        assert timings.validate < timings.overall
        assert timings.overall == (timings.parse + timings.transform + timings.validate)

    def test_parse_error_populates_exceptions_and_sets_later_phases_to_none(
        self,
        parse_and_validate_file: ParseAndValidateFile,
    ):
        result = parse_and_validate_file(
            "defin the potential position<my.domain.com:my_lib:/sub/bad>.\n"
        )

        assert result.diagnostics == []
        assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
        assert result.source is not None
        assert result.file_path == Path("sub/test.def")

        timings = result.stats
        assert timings.overall >= 0
        assert timings.parse >= 0
        assert timings.transform is None
        assert timings.validate is None
        assert timings.overall == timings.parse

    def test_invalid_utf8_populates_exceptions_and_source_is_none(
        self,
        parse_and_validate_file: ParseAndValidateFile,
    ):
        result = parse_and_validate_file(
            b"define the potential position<my.domain.com:my_lib:/sub/bad>.\n\xff"
        )

        assert result.diagnostics == []
        assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
        assert result.source is None
        assert result.file_path == Path("sub/test.def")

        timings = result.stats
        assert timings.overall >= 0
        assert timings.parse >= 0
        assert timings.transform is None
        assert timings.validate is None
        assert timings.overall == timings.parse

    def test_transform_error_from_name_parser_populates_exceptions(
        self,
        parse_and_validate_file: ParseAndValidateFile,
    ):
        source = (
            "define the potential position<"
            + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
            + ">.\n"
        )
        result = parse_and_validate_file(source)

        assert result.diagnostics == []
        assert isinstance(
            result.exception, parser_exceptions.GlobalNameInvalidFqunFormat
        )
        assert result.source == source
        assert result.file_path == Path("sub/test.def")

        timings = result.stats
        assert timings.overall >= 0
        assert timings.parse >= 0
        assert timings.transform is not None
        assert timings.transform >= 0
        assert timings.validate is None
        assert timings.overall == (timings.parse + timings.transform)


class TestPathFormats:
    def test_windows_style_string_path_still_validates_with_posix_file_path(self):
        source = "define the potential position<my.domain.com:my_lib:/sub/test>.\n"
        path = PureWindowsPath("sub\\test.def")

        with patch.object(
            validator.Validator, "_load_file", autospec=True
        ) as load_file:
            load_file.return_value = (source, None)
            results = validator.Validator().parse_and_validate_program(path=path)
            assert len(results) == 1
            result = results[0]

        assert result.diagnostics == []
        assert result.exception is None
        assert str(result.file_path) == "sub/test.def"


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
        assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
        assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
        _check_diagnostic_format(diags[1], source, 1, 43)

    def test_reserved_authority_position(self):
        source = "define the potential position<example.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_reserved_authority_with_multiverse_position(self):
        source = "define the potential position<mv:example.com:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
        _check_diagnostic_format(diags[0], source, 1, 34)

    def test_dotless_authority_position(self):
        source = "define the potential position<localhost:my_lib:/path>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.DotlessAuthorityDomainDiagnostic)
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
        diags = _parse_transform_validate(source, expected_definition_path="foo/bar")
        assert len(diags) == 0

    def test_path_mismatch_error(self):
        source = "define the potential position<my.domain.com:my_lib:/wrong/path>.\n"
        diags = _parse_transform_validate(source, expected_definition_path="foo/bar")
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.PathMismatchDiagnostic)
        assert diags[0].expected_path == "/foo/bar"
        assert diags[0].actual_path == "/wrong/path"
        _check_diagnostic_format(diags[0], source, 1, 31)

    def test_no_file_path_skips_validation(self):
        source = "define the potential position<my.domain.com:my_lib:/any/path>.\n"
        diags = _parse_transform_validate(source, expected_definition_path=None)
        assert len(diags) == 0

    def test_nested_path_matches(self):
        source = "define the potential position<my.domain.com:my_lib:/a/b/c>.\n"
        diags = _parse_transform_validate(source, expected_definition_path="a/b/c")
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
        assert isinstance(diags[0], diagnostics.UniverseNameInvalidCharDiagnostic)
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


class TestLocalNameConflicts:
    def test_different_names_no_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "define the position<beta>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_duplicate_name_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].local_name == "alpha"
        assert diags[0].first_definition_line == 2
        _check_diagnostic_format(diags[0], source, 3, 21)

    def test_three_locals_two_same_one_diagnostic(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "define the position<beta>.\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].local_name == "alpha"
        assert diags[0].first_definition_line == 2

    def test_three_same_name_two_diagnostics(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "define the position<alpha>.\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].first_definition_line == 2
        assert diags[1].first_definition_line == 2

    def test_terminated_action_no_error(self):
        source = "define the potential action<my.domain.com:my_lib:/act>.\n"
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_single_local_no_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_separate_actions_same_local_name_no_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act_one> {\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
            "define the potential action<my.domain.com:my_lib:/act_two> {\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_action_statements_local_name_no_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "it happens when {\n"
            "} and it does {\n"
            "define the position<alpha>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 0

    def test_action_statements_duplicate_name_error(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "it happens when {\n"
            "} and it does {\n"
            "define the position<alpha>.\n"
            "define the position<alpha>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].local_name == "alpha"
        assert diags[0].first_definition_line == 4
        _check_diagnostic_format(diags[0], source, 5, 21)

    def test_action_statements_name_conflicts_with_parent_scope(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "define the position<alpha>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].local_name == "alpha"
        assert diags[0].first_definition_line == 2
        _check_diagnostic_format(diags[0], source, 5, 21)

    def test_action_statements_two_duplicates_point_to_parent_scope_definition(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<alpha>.\n"
            "it happens when {\n"
            "} and it does {\n"
            "define the position<alpha>.\n"
            "define the position<alpha>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 2
        assert isinstance(diags[0], diagnostics.LocalNameConflictDiagnostic)
        assert isinstance(diags[1], diagnostics.LocalNameConflictDiagnostic)
        assert diags[0].local_name == "alpha"
        assert diags[1].local_name == "alpha"
        assert diags[0].first_definition_line == 2
        assert diags[1].first_definition_line == 2
        _check_diagnostic_format(diags[0], source, 5, 21)
        _check_diagnostic_format(diags[1], source, 6, 21)


class TestPositionConstraintReferences:
    def test_position_constraint_reference_with_invalid_path(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/root> {\n"
            "it may only contain dimension points where {\n"
            "it has the position</Bad>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(
            diags[0], diagnostics.InvalidGlobalNamePathCharacterDiagnostic
        )
        assert diags[0].segment == "Bad"
        _check_diagnostic_format(diags[0], source, 3, 22)

    def test_same_fqun_constraint_reference_must_use_short_form(self):
        source = (
            "define the potential position<my.domain.com:my_lib:/root> {\n"
            "it may only contain dimension points where {\n"
            "it has the position<my.domain.com:my_lib:/child>.\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(
            diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
        )
        assert diags[0].fqun == "my.domain.com:my_lib"
        _check_diagnostic_format(diags[0], source, 3, 21)

    def test_same_fqun_constraint_reference_in_local_position_must_use_short_form(self):
        source = (
            "define the potential action<my.domain.com:my_lib:/act> {\n"
            "define the position<my_pos> {\n"
            "it may only contain dimension points where {\n"
            "it has the position<my.domain.com:my_lib:/child>.\n"
            "}\n"
            "}\n"
            "it happens when {\n"
            "} and it does {\n"
            "}\n"
            "}\n"
        )
        diags = _parse_transform_validate(source)
        assert len(diags) == 1
        assert isinstance(
            diags[0], diagnostics.GlobalReferenceMustUseShortFormDiagnostic
        )
        assert diags[0].fqun == "my.domain.com:my_lib"
        _check_diagnostic_format(diags[0], source, 4, 21)


class TestFileNotFound:
    def test_entrypoint_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        results = validator.Validator().parse_and_validate_program(
            Path("nonexistent.def")
        )
        assert len(results) == 1
        assert isinstance(results[0].exception, FileNotFoundError)
        assert results[0].diagnostics == []

    def test_referenced_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "it may only contain dimension points where {\n"
            "it has the position</missing>.\n"
            "}\n"
            "}\n"
        )
        source_path = tmp_path / "test.def"
        _ = source_path.write_text(source, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        results = validator.Validator().parse_and_validate_program(
            Path("test.def"),
            expected_universe_name="my.domain.com:my_lib",
        )
        assert len(results) == 1
        assert results[0].exception is None
        assert len(results[0].diagnostics) == 1
        diag = results[0].diagnostics[0]
        assert isinstance(diag, diagnostics.ReferencedFileNotFoundDiagnostic)
        assert diag.path == "/missing"
        _check_diagnostic_format(diag, source, 3, 21)


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
            if isinstance(d, diagnostics.MultiverseNameInvalidCharDiagnostic)
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
            if isinstance(d, diagnostics.AuthorityDomainInvalidCharDiagnostic)
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
            if isinstance(d, diagnostics.UniverseNameInvalidCharDiagnostic)
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
            if isinstance(d, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
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
