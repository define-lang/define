# pyright: reportUnusedCallResult=false
"""Tests for CLI argument parsing.

All Driver behavior is mocked out here. Driver behavior itself is tested
in the driver tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click.testing

from define.compiler import constants, driver, main, overall_stats

_USAGE_ERROR = 2
_runner = click.testing.CliRunner()


class TestNoSubcommand:
    def test_no_args_shows_help(self):
        result = _runner.invoke(main.main, [])
        assert result.exit_code == 0
        assert "Usage" in result.output


class TestValidateSubcommand:
    def test_no_args_shows_error(self):
        result = _runner.invoke(main.main, ["validate"])
        assert result.exit_code == _USAGE_ERROR

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_alone_passes_overall_mode(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["validate", "test.dfn", "--stats"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.OVERALL
        assert call_kwargs.kwargs["stats_stream"] is not None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_per_file_passes_per_file_mode(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["validate", "test.dfn", "--stats=per-file"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.PER_FILE
        assert call_kwargs.kwargs["stats_stream"] is not None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_no_stats_passes_none_stream(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["validate", "test.dfn"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_stream"] is None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_without_value_before_file_uses_flag_value(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["validate", "test.dfn", "--stats"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.OVERALL

    def test_stats_with_non_choice_value_shows_error(self):
        result = _runner.invoke(main.main, ["validate", "--stats", "test.dfn"])
        assert result.exit_code == _USAGE_ERROR
        assert "is not one of" in result.output

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_file_path_is_passed_to_driver(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["validate", "my/file.dfn"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_args = mock_run.call_args
        assert call_args.args[1] == Path("my/file.dfn")

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_mode_is_validate(self, mock_run: MagicMock):
        _runner.invoke(main.main, ["validate", "test.dfn"])
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["mode"] == driver.DriverMode.VALIDATE


class TestCompileSubcommand:
    def test_no_args_shows_error(self):
        result = _runner.invoke(main.main, ["compile"])
        assert result.exit_code == _USAGE_ERROR

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_mode_is_compile(self, mock_run: MagicMock):
        _runner.invoke(main.main, ["compile", "test.dfn"])
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["mode"] == driver.DriverMode.COMPILE

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_file_path_is_passed_to_driver(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["compile", "my/file.dfn"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_args = mock_run.call_args
        assert call_args.args[1] == Path("my/file.dfn")

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_passes_overall_mode(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["compile", "test.dfn", "--stats"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.OVERALL
        assert call_kwargs.kwargs["stats_stream"] is not None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_default_output_dir(self, mock_run: MagicMock):
        _runner.invoke(main.main, ["compile", "test.dfn"])
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["output_dir"] == constants.DEFAULT_OUTPUT_DIR

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_custom_output_dir(self, mock_run: MagicMock):
        _runner.invoke(main.main, ["compile", "test.dfn", "--out", "my/output"])
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["output_dir"] == Path("my/output")
