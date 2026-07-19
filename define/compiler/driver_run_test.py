"""Tests for Driver.run().

Most integration tests for the driver should be in driver_integration_test,
intead.

This just tests a few cases to make sure that the specific code in Driver.run
is functioning correctly.
"""

import io
from pathlib import Path

import pytest

from define.compiler import constants, driver, overall_stats, parser

_PARSER = parser.Parser()


def test_absolute_path_outside_project_root_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside_path = tmp_path / "outside.dfn"
    monkeypatch.chdir(project_root)

    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(outside_path, error_stream=error_stream)

    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        f"Absolute path is outside the project root: {outside_path}\n"
        f"  Resolved to: {outside_path}\n"
        f"  Project root: {project_root}\n"
        f"For more information, see {constants.DOCS_ROOT}/project-root.md\n"
    )


def test_invalid_config_returns_error_and_prints_to_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text("project: {}\n")
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n"
    )
    monkeypatch.chdir(tmp_path)

    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(Path("test.dfn"), error_stream=error_stream)
    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        'File ".define/project/config.defcl"\n'
        "Invalid configuration:\n"
        "  - project.universe_name: value is required\n"
    )


def test_invalid_config_without_error_stream_prints_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text("project: {}\n")
    _ = (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n"
    )
    monkeypatch.chdir(tmp_path)

    result = driver.Driver(_PARSER).run(Path("test.dfn"))

    captured = capsys.readouterr()
    assert result == driver.ExitCode.ERROR
    assert captured.out == ""
    assert captured.err == (
        'File ".define/project/config.defcl"\n'
        "Invalid configuration:\n"
        "  - project.universe_name: value is required\n"
    )


def test_valid_file_returns_success(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(Path("test.dfn"), error_stream=error_stream)
    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""


def test_relative_path_outside_project_root_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside_path = tmp_path / "outside.dfn"
    monkeypatch.chdir(project_root)

    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("../outside.dfn"), error_stream=error_stream
    )

    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        "Relative path resolves to outside the project root: ../outside.dfn\n"
        f"  Resolved to: {outside_path}\n"
        f"  Project root: {project_root}\n"
        f"For more information, see {constants.DOCS_ROOT}/project-root.md\n"
    )


def test_syntax_error_returns_error_and_prints_to_stream(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        error_stream=error_stream,
    )
    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        'File "test.dfn", line 1, column 1\n'
        "defin the potential position<mv:define-l\n"
        "^\n"
        "Expected a global definition like 'define the potential ...'\n"
    )


def test_validation_diagnostics_returns_error_and_prints_to_stream(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("wrong_file.dfn"),
        error_stream=error_stream,
    )
    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        'File "wrong_file.dfn", line 1, column 60\n'
        "define the potential position<mv:define-lang.org:test_path:/different>.\n"
        "                                                           ^\n"
        "definition path '/different' does not match file path '/wrong_file'\n"
    )


def test_multiple_errors_are_separated_by_divider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        'project: { universe_name: "mv:define-lang.org:test_path" }\n'
    )
    _ = (tmp_path / "wrong_file.dfn").write_text(
        "define the potential position<mv:define-lang.org:test_path:/first>.\n"
        + "define the potential position<mv:define-lang.org:test_path:/second>.\n"
    )
    monkeypatch.chdir(tmp_path)

    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("wrong_file.dfn"), error_stream=error_stream
    )
    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        (
            'File "wrong_file.dfn", line 1, column 60\n'
            "define the potential position<mv:define-lang.org:test_path:/first>.\n"
            "                                                           ^\n"
            "definition path '/first' does not match file path '/wrong_file'"
        )
        + constants.ERROR_DIVIDER
        + (
            'File "wrong_file.dfn", line 2, column 60\n'
            "define the potential position<mv:define-lang.org:test_path:/second>.\n"
            "                                                           ^\n"
            "definition path '/second' does not match file path '/wrong_file'"
        )
        + "\n"
    )


def test_stats_stream_receives_output(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    stats_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        stats_stream=stats_stream,
        stats_mode=overall_stats.StatsMode.OVERALL,
    )
    assert result == driver.ExitCode.SUCCESS
    output = stats_stream.getvalue()
    assert "--- Compilation Stats ---" in output
    assert "-- Overall --" in output
    assert "-- Breakdown --" in output


def test_stats_stream_none_produces_no_stats(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(Path("test.dfn"), error_stream=error_stream)
    assert result == driver.ExitCode.SUCCESS
    assert "Compilation Stats" not in error_stream.getvalue()


def test_compile_succeeds(
    testdata_project_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        mode=driver.DriverMode.COMPILE,
        output_dir=tmp_path,
    )
    assert result == driver.ExitCode.SUCCESS


def test_compile_with_errors_returns_error(
    testdata_project_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        mode=driver.DriverMode.COMPILE,
        error_stream=io.StringIO(),
        output_dir=tmp_path,
    )
    assert result == driver.ExitCode.ERROR


def test_compile_emits_codegen_diagnostic_on_action_entry_point(
    testdata_project_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        mode=driver.DriverMode.COMPILE,
        error_stream=error_stream,
        output_dir=tmp_path,
    )
    assert result == driver.ExitCode.ERROR
    assert error_stream.getvalue() == (
        'File "test.dfn", line 1, column 1\n'
        "define the potential action<mv:define-lang.org:test_action:/test> {\n"
        "^\n"
        "the entry point of a Define program must be a constructor\n"
    )
