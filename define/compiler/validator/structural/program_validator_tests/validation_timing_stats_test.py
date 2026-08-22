# pyright: reportUnusedCallResult=false
"""Parse and validate file validation timing tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from define.compiler.validator import stats
from define.compiler.validator import test_helpers as validator_test_helpers
from define.compiler.validator.structural import program_validator
from define.compiler.validator.structural.program_validator_tests import (
    test_helpers,
)

if TYPE_CHECKING:
    import pytest


def _assert_overall_equals_phase_sum(timings: stats.ValidationTimingStats):
    phase_sum = (
        timings.file_loading
        + timings.parse
        + timings.file_validation
        + timings.global_validation
    )
    assert timings.overall_compile == phase_sum


def test_successful_validation_records_all_phase_timings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation > 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_parse_error_sets_file_validation_phase_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = test_helpers.parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n",
        tmp_path,
        monkeypatch,
    )

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_invalid_utf8_sets_parse_and_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    result = test_helpers.parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff",
        tmp_path,
        monkeypatch,
    )

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse == 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_name_parser_error_at_definition_sets_file_validation_phase_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = (
        "define the potential position<"
        + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
        + ">.\n"
    )
    result = test_helpers.parse_and_validate_file(source, tmp_path, monkeypatch)

    timings = result.stats
    assert timings.overall_compile > 0

    assert timings.file_loading > 0
    assert timings.parse > 0
    assert timings.file_validation == 0
    assert timings.queue_wait > 0
    _assert_overall_equals_phase_sum(timings)


def test_config_error_sets_all_phases_to_zero(
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
    timings = results[0].stats

    assert timings.file_loading == 0
    assert timings.parse == 0
    assert timings.file_validation == 0
    assert timings.queue_wait == 0
    _assert_overall_equals_phase_sum(timings)


def test_file_not_found_sets_parse_and_later_phases_to_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    validator_test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
    relative_path = PurePosixPath("nonexistent.dfn")
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(relative_path)
        .file_results
    )
    assert len(results) == 1
    timings = results[0].stats

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
    validator_test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
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
