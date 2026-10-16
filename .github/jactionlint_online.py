"""Run every jactionlint rule, including those that ask the GitHub API."""

from __future__ import annotations

import os
import subprocess
import sys

from tools import runfiles


def main():
    """Lint the workspace's GitHub workflows."""
    jactionlint, shellcheck, ruff = (
        runfiles.resolve(location) for location in sys.argv[1:]
    )
    # Without file arguments jactionlint checks the whole repository, which it
    # needs before it reports an entry of "ignores:" as unused.
    result = subprocess.run(
        [
            jactionlint,
            "--no-color",
            "--online=strict",
            "--strict-exit",
            f"--shellcheck={shellcheck}",
            f"--ruff={ruff}",
        ],
        cwd=os.environ["BUILD_WORKSPACE_DIRECTORY"],
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
