"""Tests for Driver.run().

Most integration tests for the driver should be in driver_integration_test,
intead.

This just tests a few cases to make sure that the specific code in Driver.run
is functioning correctly.
"""

import io
from pathlib import Path

import pytest

from define.compiler import constants, driver, overall_stats

TESTDATA_ROOT = Path("define/testdata")
FILES_ROOT = TESTDATA_ROOT / "files"
PROJECTS_ROOT = TESTDATA_ROOT / "projects"


class TestRun:
    def test_absolute_path_outside_project_root_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_path = tmp_path / "outside.def"
        monkeypatch.chdir(project_root)

        error_stream = io.StringIO()
        result = driver.Driver().run(outside_path, error_stream=error_stream)

        assert result == driver.ExitCode.ERROR
        assert error_stream.getvalue() == (
            f"Absolute path is outside the project root: {outside_path}\n"
            f"  Resolved to: {outside_path}\n"
            f"  Project root: {project_root}\n"
            f"For more information, see {constants.DOCS_ROOT}/project-root.md\n"
        )

    def test_invalid_config_returns_error_and_prints_to_stream(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text("project: {}\n")
        _ = (tmp_path / "test.def").write_text(
            "define the potential position<x.com:lib:/test>.\n"
        )
        monkeypatch.chdir(tmp_path)

        error_stream = io.StringIO()
        result = driver.Driver().run(Path("test.def"), error_stream=error_stream)
        assert result == driver.ExitCode.ERROR
        assert error_stream.getvalue() == (
            'File ".define/project/config.defcl"\n'
            "Invalid configuration:\n"
            "  - project.universe_name: value is required\n"
        )

    def test_invalid_config_without_error_stream_prints_to_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config_dir = tmp_path / ".define" / "project"
        config_dir.mkdir(parents=True)
        _ = (config_dir / "config.defcl").write_text("project: {}\n")
        _ = (tmp_path / "test.def").write_text(
            "define the potential position<x.com:lib:/test>.\n"
        )
        monkeypatch.chdir(tmp_path)

        result = driver.Driver().run(Path("test.def"))

        captured = capsys.readouterr()
        assert result == driver.ExitCode.ERROR
        assert captured.out == ""
        assert captured.err == (
            'File ".define/project/config.defcl"\n'
            "Invalid configuration:\n"
            "  - project.universe_name: value is required\n"
        )

    def test_valid_file_returns_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "valid" / "position_definition")
        error_stream = io.StringIO()
        result = driver.Driver().run(Path("test.def"), error_stream=error_stream)
        assert result == driver.ExitCode.SUCCESS
        assert error_stream.getvalue() == ""

    def test_relative_path_outside_project_root_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_path = tmp_path / "outside.def"
        monkeypatch.chdir(project_root)

        error_stream = io.StringIO()
        result = driver.Driver().run(Path("../outside.def"), error_stream=error_stream)

        assert result == driver.ExitCode.ERROR
        assert error_stream.getvalue() == (
            "Relative path resolves to outside the project root: ../outside.def\n"
            f"  Resolved to: {outside_path}\n"
            f"  Project root: {project_root}\n"
            f"For more information, see {constants.DOCS_ROOT}/project-root.md\n"
        )

    def test_syntax_error_returns_error_and_prints_to_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(FILES_ROOT)
        error_stream = io.StringIO()
        result = driver.Driver().run(
            Path("invalid/syntax/keywords/misspelled_define.def"),
            error_stream=error_stream,
        )
        assert result == driver.ExitCode.ERROR
        assert error_stream.getvalue() == (
            'File "invalid/syntax/keywords/misspelled_define.def", line 1, column 1\n'
            "defin the potential position<mv:define-l\n"
            "^\n"
            "Expected a global definition like 'define the potential ...'\n"
        )

    def test_validation_diagnostics_returns_error_and_prints_to_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "invalid" / "syntax" / "path_mismatch")
        error_stream = io.StringIO()
        result = driver.Driver().run(
            Path("wrong_file.def"),
            error_stream=error_stream,
        )
        assert result == driver.ExitCode.ERROR
        assert error_stream.getvalue() == (
            'File "wrong_file.def", line 1, column 60\n'
            "define the potential position<mv:define-lang.org:test_path:/different>.\n"
            "                                                           ^\n"
            "definition path '/different' does not match file path '/wrong_file'\n"
        )

    def test_stats_stream_receives_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "valid" / "position_definition")
        stats_stream = io.StringIO()
        result = driver.Driver().run(
            Path("test.def"),
            stats_stream=stats_stream,
            stats_mode=overall_stats.StatsMode.OVERALL,
        )
        assert result == driver.ExitCode.SUCCESS
        output = stats_stream.getvalue()
        assert "--- Compilation Stats ---" in output
        assert "-- Overall --" in output
        assert "-- Breakdown --" in output

    def test_stats_stream_none_produces_no_stats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "valid" / "position_definition")
        error_stream = io.StringIO()
        result = driver.Driver().run(Path("test.def"), error_stream=error_stream)
        assert result == driver.ExitCode.SUCCESS
        assert "Compilation Stats" not in error_stream.getvalue()

    def test_compile_succeeds(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "valid" / "position_definition")
        result = driver.Driver().run(
            Path("test.def"),
            mode=driver.DriverMode.COMPILE,
            output_dir=tmp_path,
        )
        assert result == driver.ExitCode.SUCCESS

    def test_compile_with_errors_returns_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(FILES_ROOT)
        result = driver.Driver().run(
            Path("invalid/syntax/keywords/misspelled_define.def"),
            mode=driver.DriverMode.COMPILE,
            error_stream=io.StringIO(),
            output_dir=tmp_path,
        )
        assert result == driver.ExitCode.ERROR
