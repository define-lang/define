"""Tests for CLI argument parsing.

All Driver behavior is mocked out here. Driver behavior itself is tested
in the driver tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click.testing

from define.compiler import driver, main, overall_stats

_USAGE_ERROR = 2
_runner = click.testing.CliRunner()


class TestMainCli:
    def test_no_args_shows_error(self):
        result = _runner.invoke(main.main, [])
        assert result.exit_code == _USAGE_ERROR

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_alone_passes_overall_mode(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["test.def", "--stats"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.OVERALL
        assert call_kwargs.kwargs["stats_stream"] is not None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_per_file_passes_per_file_mode(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["test.def", "--stats=per-file"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.PER_FILE
        assert call_kwargs.kwargs["stats_stream"] is not None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_no_stats_passes_none_stream(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["test.def"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_stream"] is None

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_stats_without_value_before_file_uses_flag_value(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["test.def", "--stats"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs["stats_mode"] == overall_stats.StatsMode.OVERALL

    def test_stats_with_non_choice_value_shows_error(self):
        result = _runner.invoke(main.main, ["--stats", "test.def"])
        assert result.exit_code == _USAGE_ERROR
        assert "is not one of" in result.output

    @patch.object(
        driver.Driver, "run", autospec=True, return_value=driver.ExitCode.SUCCESS
    )
    def test_file_path_is_passed_to_driver(self, mock_run: MagicMock):
        result = _runner.invoke(main.main, ["my/file.def"])
        assert result.exit_code == driver.ExitCode.SUCCESS
        call_args = mock_run.call_args
        assert call_args.args[1] == Path("my/file.def")
