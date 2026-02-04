#!/usr/bin/env python3
"""Run CI checks in parallel and report results via GitHub Checks API."""

import glob
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHECK_TIMEOUT_SECONDS = 600
TIMEOUT_EXIT_CODE = 124
ERROR_EXIT_CODE = 1
REPORTING_ERROR_EXIT_CODE = 2
SUCCESS_EXIT_CODE = 0
GITHUB_API_TEXT_LIMIT = 65000
API_REQUEST_TIMEOUT_SECONDS = 10


@dataclass
class Check:
    """Definition of a check to run."""

    name: str
    command: list[str]
    report_to_github: bool = True


@dataclass
class CheckResult:
    """Result of running a check."""

    check: Check
    exit_code: int
    output: str


# Define all checks here - add new checks by adding a Check() entry
CHECKS = [
    Check(
        name="Prettier",
        command=["npx", "prettier", "--check", "**/*.md", "**/*.yaml"],
    ),
    Check(
        name="Ruff",
        command=["ruff", "check"],
    ),
    Check(
        name="Ruff Format",
        command=["ruff", "format", "--check", "--diff"],
    ),
    Check(
        name="Pyright",
        command=["uv", "run", "pyright"],
    ),
    Check(
        name="Pytest",
        command=["uv", "run", "pytest", "--junit-xml=pytest-results.xml"],
        report_to_github=False,
    ),
    Check(
        name="Proposal Validation",
        command=[
            "uv",
            "run",
            "python",
            "scripts/validate_proposals.py",
            "proposals/0*.md",
            "defcl/proposals/0*.md",
        ],
    ),
    Check(
        name="Cursor Permissions",
        command=[
            "uv",
            "run",
            "python",
            "scripts/sync_cursor_permissions.py",
            "--check",
        ],
    ),
]


def run_check(check: Check, timeout: float = CHECK_TIMEOUT_SECONDS) -> CheckResult:
    """Run a single check and return its result."""
    expanded_command = []
    for arg in check.command:
        expanded = glob.glob(arg)
        if expanded:
            expanded_command.extend(sorted(expanded))
        else:
            expanded_command.append(arg)

    try:
        result = subprocess.run(
            expanded_command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CheckResult(
            check=check,
            exit_code=result.returncode,
            output=result.stdout + result.stderr,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            check=check,
            exit_code=TIMEOUT_EXIT_CODE,
            output=f"Check timed out after {timeout} seconds",
        )
    except (OSError, ValueError) as e:
        return CheckResult(check=check, exit_code=ERROR_EXIT_CODE, output=str(e))


def create_check_run(
    check: Check,
    conclusion: str,
    output_text: str,
    token: str,
    repo: str,
    sha: str,
) -> bool:
    """Create a check run via GitHub Checks API.

    Returns True if successful, False otherwise.
    """
    if not check.report_to_github:
        return True

    if len(output_text) > GITHUB_API_TEXT_LIMIT:
        logger.warning(
            "Output for %s exceeds GitHub API limit (%d > %d), truncating",
            check.name,
            len(output_text),
            GITHUB_API_TEXT_LIMIT,
        )
        output_text = output_text[:GITHUB_API_TEXT_LIMIT]

    url = f"https://api.github.com/repos/{repo}/check-runs"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "name": check.name,
        "head_sha": sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": check.name,
            "summary": check.name,
            "text": output_text,
        },
    }

    try:
        response = requests.post(
            url, headers=headers, json=payload, timeout=API_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        logger.exception("Failed to create check run for %s", check.name)
        return False


def run_checks(
    checks: list[Check],
    token: str,
    repo: str,
    sha: str,
) -> int:
    """Run all checks in parallel and report results."""
    if not token or not repo or not sha:
        logger.error(
            "Missing required environment variables (GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_SHA)"
        )
        return ERROR_EXIT_CODE

    logger.info("Running %d checks in parallel...", len(checks))

    results: list[CheckResult] = []
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        future_to_check = {executor.submit(run_check, check): check for check in checks}
        for future in as_completed(future_to_check):
            result = future.result()
            results.append(result)
            status = "✓" if result.exit_code == SUCCESS_EXIT_CODE else "✗"
            logger.info(
                "%s %s (exit code: %d)", status, result.check.name, result.exit_code
            )
            if result.output:
                logger.info("Output from %s:\n%s", result.check.name, result.output)

    logger.info("Reporting results to GitHub...")
    reporting_failures = []
    for result in results:
        conclusion = "success" if result.exit_code == SUCCESS_EXIT_CODE else "failure"
        succeeded = create_check_run(
            result.check,
            conclusion,
            result.output,
            token,
            repo,
            sha,
        )
        if not succeeded:
            reporting_failures.append(result.check.name)

    failed_checks = [
        result.check.name for result in results if result.exit_code != SUCCESS_EXIT_CODE
    ]
    if reporting_failures:
        logger.error(
            "Failed to report checks to GitHub: %s", ", ".join(reporting_failures)
        )
        return REPORTING_ERROR_EXIT_CODE

    if failed_checks:
        logger.error("Failed checks: %s", ", ".join(failed_checks))
        return ERROR_EXIT_CODE

    logger.info("All checks passed!")
    return 0


def main() -> int:
    """Collect environment variables and run checks."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    return run_checks(CHECKS, token, repo, sha)


if __name__ == "__main__":
    sys.exit(main())
