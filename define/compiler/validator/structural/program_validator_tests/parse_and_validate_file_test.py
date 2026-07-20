# pyright: reportUnusedCallResult=false
"""Parse and validate file tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

# TODO: Rename this file to reflect its responsibilities, or split its result
# and exception coverage from its validation timing coverage.

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import config, exceptions, parser, parser_exceptions
from define.compiler.data_structures import define_path
from define.compiler.validator import stats, test_helpers, validation_result
from define.compiler.validator.structural import program_validator

_PARSER = parser.Parser()


def _parse_and_validate_file(
    source: str | bytes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> validation_result.FileValidationResult:
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    if isinstance(source, str):
        source_path.write_text(source, encoding="utf-8")
    else:
        source_path.write_bytes(source)
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator(_PARSER)
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    return results[0]


def _assert_overall_equals_phase_sum(timings: stats.ValidationTimingStats):
    phase_sum = (
        timings.file_loading
        + timings.parse
        + timings.file_validation
        + timings.global_validation
    )
    assert timings.overall_compile == phase_sum


def test_returns_single_file_timing_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = _parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert result.exception is None
    assert result.source == source
    assert result.file_path == define_path.DefinePath("test.dfn")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation > 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_parse_error_populates_exceptions_and_sets_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n",
        tmp_path,
        monkeypatch,
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.source is not None
    assert result.file_path == define_path.DefinePath("test.dfn")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_non_filesystem_parse_error_returns_single_result():
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program_non_filesystem(
            "defin the potential position<my.domain.com:my_lib:/bad>.\n"
        )
        .file_results
    )

    assert len(results) == 1
    result = results[0]
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.diagnostics == []


def test_invalid_utf8_populates_exceptions_and_source_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = _parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff",
        tmp_path,
        monkeypatch,
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.source is None
    assert result.file_path == define_path.DefinePath("test.dfn")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_name_parser_error_at_definition_populates_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<"
        + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
        + ">.\n"
    )
    result = _parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.source == source
    assert result.file_path == define_path.DefinePath("test.dfn")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_name_parser_error_at_reference_populates_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<my.domain.com:my_lib:/test> {\n"
        "    it may only contain particles where {\n"
        "        it has the position<mv:too:many:colons:bad:/y>.\n"
        "    }\n"
        "}\n"
    )
    result = _parse_and_validate_file(source, tmp_path, monkeypatch)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.exception.context == "mv:too:many:colons:bad:/y"
    assert result.exception.line == 3
    assert result.exception.column == 29
    assert result.exception.file_path == PurePosixPath("test.dfn")


def test_config_error_sets_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, config.ConfigError)
    assert result.file_path == define_path.DefinePath("test.dfn")
    assert result.root_prefix == define_path.EMPTY

    timings = result.stats

    assert timings.file_loading == 0
    assert timings.parse == 0
    assert timings.file_validation == 0
    assert timings.queue_wait == 0
    _assert_overall_equals_phase_sum(timings)


def test_file_not_found_sets_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    relative_path = PurePosixPath("nonexistent.dfn")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, exceptions.SourceFileNotFoundError)

    timings = result.stats

    assert timings.file_loading > 0
    assert timings.parse == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_config_loading_time_ns_tracks_successful_root_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)

    validator = program_validator.ProgramStructuralValidator()
    program_result = validator.validate_program(relative_path)

    assert program_result.config_loading_time_ns > 0


def test_config_loading_time_ns_tracks_failing_root_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.dfn")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    validator = program_validator.ProgramStructuralValidator()
    program_result = validator.validate_program(relative_path)

    assert program_result.config_loading_time_ns > 0
