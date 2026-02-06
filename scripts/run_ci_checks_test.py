"""Tests for run_ci_checks.py."""

import os
import tempfile
from unittest.mock import patch

import requests
from scripts import run_ci_checks


def _make_check(name: str, command: list[str]) -> run_ci_checks.Check:
    return run_ci_checks.Check(name=name, command=command, report_to_github=False)


def test_run_check_success():
    check = _make_check("Test Check", ["echo", "hello"])
    result = run_ci_checks.run_check(check)
    assert result.check == check
    assert result.exit_code == run_ci_checks.SUCCESS_EXIT_CODE
    assert "hello" in result.output


def test_run_check_failure():
    check = _make_check("Test Check", ["false"])
    result = run_ci_checks.run_check(check)
    assert result.check == check
    assert result.exit_code == run_ci_checks.ERROR_EXIT_CODE


def test_run_check_timeout():
    check = _make_check("Test Check", ["sleep", "2"])
    result = run_ci_checks.run_check(check, timeout=0.01)
    assert result.exit_code == run_ci_checks.TIMEOUT_EXIT_CODE
    assert "timed out" in result.output.lower()


def test_run_checks_success():
    test_checks = [
        _make_check("Success Check 1", ["echo", "success1"]),
        _make_check("Success Check 2", ["echo", "success2"]),
    ]

    result = run_ci_checks.run_checks(
        test_checks,
        token="test-token",  # noqa: S106 - not a real password
        repo="test/repo",
        sha="abc123",
    )
    assert result == run_ci_checks.SUCCESS_EXIT_CODE


def test_run_checks_with_failures():
    test_checks = [
        _make_check("Failure Check 1", ["false"]),
        _make_check("Failure Check 2", ["false"]),
    ]

    result = run_ci_checks.run_checks(
        test_checks,
        token="test-token",  # noqa: S106 - not a real password
        repo="test/repo",
        sha="abc123",
    )
    assert result == run_ci_checks.ERROR_EXIT_CODE


def test_run_check_expands_glob_patterns():
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "data")
        os.makedirs(subdir)
        for name in ["00001-first.md", "00002-second.md", "other.txt"]:
            open(os.path.join(subdir, name), "w").close()

        orig_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            check = _make_check("Glob Expansion Test", ["ls", "data/0000*.md"])
            result = run_ci_checks.run_check(check)
            assert result.exit_code == 0
            output_lines = result.output.strip().split("\n")
            assert len(output_lines) == 2
            assert all(
                line.startswith("data/0000") and line.endswith(".md")
                for line in output_lines
            )
            assert "data/00001-first.md" in output_lines
        finally:
            os.chdir(orig_cwd)


def test_run_checks_with_reporting_failure():
    test_checks = [
        run_ci_checks.Check(
            "Success Check", ["echo", "success"], report_to_github=True
        ),
    ]

    with patch.object(run_ci_checks.requests, "post", autospec=True) as mock_post:
        mock_post.side_effect = requests.RequestException("API failure")
        result = run_ci_checks.run_checks(
            test_checks,
            token="test-token",  # noqa: S106 - not a real password
            repo="test/repo",
            sha="abc123",
        )
        assert result == run_ci_checks.REPORTING_ERROR_EXIT_CODE


def test_run_check_with_working_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = os.path.join(tmpdir, "mysubdir")
        os.makedirs(subdir)

        orig_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            check = run_ci_checks.Check(
                name="Working Directory Test",
                command=["pwd"],
                report_to_github=False,
                working_directory="mysubdir",
            )
            result = run_ci_checks.run_check(check)
            assert result.exit_code == run_ci_checks.SUCCESS_EXIT_CODE
            assert result.output.strip().endswith("/mysubdir")
        finally:
            os.chdir(orig_cwd)
