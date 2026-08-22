"""Exercise the Driver's public boundary across every compiler phase.

These tests use Driver.run for both filesystem projects and direct source so a
wiring change cannot silently omit validation, code generation, diagnostics,
or statistics. Together they cover every publicly reachable line and branch in
driver.py.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from define.compiler import constants, driver, overall_stats, parser

_PARSER = parser.Parser()


def _write_valid_position_project(project_root: Path, universe_name: str) -> None:
    config_dir = project_root / ".define" / "project"
    config_dir.mkdir(parents=True)
    _ = (config_dir / "config.defcl").write_text(
        f'project: {{ universe_name: "{universe_name}" }}\n'
    )
    _ = (project_root / "test.dfn").write_text(
        f"define the potential position<{universe_name}:/test>.\n"
    )


def test_absolute_path_in_project_returns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_valid_position_project(
        project_root, "mv:define-lang.org:driver_absolute_path"
    )
    monkeypatch.chdir(project_root)
    error_stream = io.StringIO()

    result = driver.Driver(_PARSER).run(
        project_root / "test.dfn",
        error_stream=error_stream,
    )

    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""


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


def test_compile_source_succeeds(tmp_path: Path) -> None:
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<created>.\n"
        "        create a particle in position<created>.\n"
        "    }\n"
        "}\n"
    )

    result = driver.Driver(_PARSER).run(
        source=source,
        mode=driver.DriverMode.COMPILE,
        output_dir=tmp_path,
    )

    assert result == driver.ExitCode.SUCCESS
    generated_entry_point = tmp_path / "__main__.py"
    assert generated_entry_point.exists()
    assert generated_entry_point.stat().st_size > 0


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


def test_compile_without_output_directory_raises_value_error() -> None:
    with pytest.raises(ValueError, match="output_dir is required when mode is COMPILE"):
        _ = driver.Driver(_PARSER).run(mode=driver.DriverMode.COMPILE)


def test_compile_without_path_or_source_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path is required when source is not given"):
        _ = driver.Driver(_PARSER).run(
            mode=driver.DriverMode.COMPILE,
            output_dir=tmp_path,
        )


def test_default_parser_returns_success() -> None:
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    error_stream = io.StringIO()

    result = driver.Driver().run(source=source, error_stream=error_stream)

    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""


def test_multifile_project_returns_success(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(testdata_project_directory)
    error_stream = io.StringIO()
    stats_stream = io.StringIO()

    result = driver.Driver(_PARSER).run(
        Path("test.dfn"),
        error_stream=error_stream,
        stats_stream=stats_stream,
        stats_mode=overall_stats.StatsMode.PER_FILE,
    )

    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""
    stats_output = stats_stream.getvalue()
    assert "Files compiled:  2" in stats_output
    assert "  test.dfn\n" in stats_output
    assert "  dependency.dfn\n" in stats_output


def test_reference_graph_diagnostic_returns_error(
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
        'File "test.dfn", line 9, column 30\n'
        "        create a particle in position<target>.\n"
        "                             ^\n"
        "a particle already exists in 'position<target>'; it was put there at:\n"
        'File "test.dfn", line 8, column 30\n'
    )


def test_relative_path_with_dotdot_in_project_returns_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_valid_position_project(
        project_root, "mv:define-lang.org:driver_relative_path"
    )
    monkeypatch.chdir(project_root)
    error_stream = io.StringIO()

    result = driver.Driver(_PARSER).run(
        Path("unused/../test.dfn"),
        error_stream=error_stream,
    )

    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""


def test_valid_source_returns_success() -> None:
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    error_stream = io.StringIO()

    result = driver.Driver(_PARSER).run(source=source, error_stream=error_stream)

    assert result == driver.ExitCode.SUCCESS
    assert error_stream.getvalue() == ""


def test_validate_without_path_or_source_raises_value_error() -> None:
    with pytest.raises(ValueError, match="path is required when source is not given"):
        _ = driver.Driver(_PARSER).run()
