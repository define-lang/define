"""Regenerate uv.lock from pyproject.toml."""

from __future__ import annotations

import os
import subprocess
import sys

from tools import runfiles


def main():
    """Run `uv lock` in the workspace."""
    uv = runfiles.resolve(sys.argv[1])
    result = subprocess.run(
        [uv, "lock"], cwd=os.environ["BUILD_WORKSPACE_DIRECTORY"], check=False
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
