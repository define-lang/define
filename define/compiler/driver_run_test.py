"""Tests for Driver.run().

Most integration tests for the driver should be in driver_integration_test,
intead.

This just tests a few cases to make sure that the specific code in Driver.run
is functioning correctly.
"""

import io
from pathlib import Path

import pytest

from define.compiler import driver

TESTDATA_ROOT = Path("define/testdata")
FILES_ROOT = TESTDATA_ROOT / "files"
PROJECTS_ROOT = TESTDATA_ROOT / "projects"


class TestRun:
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

    def test_valid_file_returns_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(PROJECTS_ROOT / "valid" / "position_definition")
        error_stream = io.StringIO()
        result = driver.Driver().run(Path("test.def"), error_stream=error_stream)
        assert result == driver.ExitCode.SUCCESS
        assert error_stream.getvalue() == ""

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
            "File has no definitions. Add at least one 'define the potential ...' line.\n"
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
            "line 1, column 31: definition path '/different' does not match file path '/wrong_file'\n"
            "  define the potential position<mv:define-lang.org:test_path:/different>.\n"
            "                                ^\n"
        )
