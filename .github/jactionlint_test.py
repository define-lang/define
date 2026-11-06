from __future__ import annotations

import os
import subprocess

from tools import runfiles


def test_workflows_and_actions_pass_jactionlint():
    files = [
        runfiles.resolve(location)
        for location in os.environ["GITHUB_ACTIONS_FILES"].split()
    ]
    result = subprocess.run(
        [
            runfiles.resolve_from_env("JACTIONLINT"),
            "--no-color",
            f"--config-file={runfiles.resolve_from_env('JACTIONLINT_CONFIG')}",
            "--no-online",
            "--strict-exit",
            f"--shellcheck={runfiles.resolve_from_env('SHELLCHECK')}",
            f"--ruff={runfiles.resolve_from_env('RUFF')}",
            *files,
        ],
        check=False,
    )
    assert result.returncode == 0
