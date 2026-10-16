from __future__ import annotations

import os
import subprocess

from tools import runfiles


def test_workflows_pass_jactionlint():
    workflows = [
        runfiles.resolve(location)
        for location in os.environ["GITHUB_WORKFLOWS"].split()
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
            *workflows,
        ],
        check=False,
    )
    assert result.returncode == 0
