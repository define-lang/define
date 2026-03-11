# pyright: reportUnusedCallResult=false
"""Parse and validate file tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import exceptions, parser_exceptions
from define.compiler.conftest import (
    ParseAndValidateFile,
)
from define.compiler.validator import program_validator, stats
from define.compiler.validator.program_validator_tests import test_helpers


def _assert_overall_equals_phase_sum(timings: stats.ValidationTimingStats):
    phase_sum = (
        timings.file_loading
        + timings.parse
        + timings.transform
        + timings.file_validation
        + timings.global_validation
        + timings.deferred_validation
    )
    assert timings.overall_compile == phase_sum


def test_returns_single_file_timing_stats(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = parse_and_validate_file(source)

    assert result.diagnostics == []
    assert result.exception is None
    assert result.source == source
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.transform > 0
    assert timings.file_validation > 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_parse_error_populates_exceptions_and_sets_later_phases_to_zero(
    parse_and_validate_file: ParseAndValidateFile,
):
    result = parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n"
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.source is not None
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.transform == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_non_filesystem_parse_error_returns_single_result():
    results = (
        program_validator.ProgramValidator()
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
    parse_and_validate_file: ParseAndValidateFile,
):
    result = parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff"
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.source is None
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse == 0
    assert timings.transform == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_transform_error_from_name_parser_populates_exceptions(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<"
        + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
        + ">.\n"
    )
    result = parse_and_validate_file(source)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.source == source
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.transform > 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_config_error_sets_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.def")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, exceptions.ConfigError)
    assert result.file_path == PurePosixPath("test.def")
    assert result.root_prefix == PurePosixPath(".")

    timings = result.stats

    assert timings.file_loading == 0
    assert timings.parse == 0
    assert timings.transform == 0
    assert timings.file_validation == 0
    assert timings.queue_wait == 0
    _assert_overall_equals_phase_sum(timings)


def test_file_not_found_sets_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    relative_path = PurePosixPath("nonexistent.def")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    result = results[0]

    assert isinstance(result.exception, exceptions.SourceFileNotFoundError)

    timings = result.stats

    assert timings.file_loading > 0
    assert timings.parse == 0
    assert timings.transform == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_config_loading_time_ns_tracks_successful_root_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.def")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    monkeypatch.chdir(tmp_path)

    validator = program_validator.ProgramValidator()
    program_result = validator.validate_program(relative_path)

    assert program_result.config_loading_time_ns > 0


def test_config_loading_time_ns_tracks_failing_root_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    relative_path = PurePosixPath("test.def")
    source_path = tmp_path / relative_path
    source_path.write_text(
        "define the potential position<my.domain.com:my_lib:/test>.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    validator = program_validator.ProgramValidator()
    program_result = validator.validate_program(relative_path)

    assert program_result.config_loading_time_ns > 0
