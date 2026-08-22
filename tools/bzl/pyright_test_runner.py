"""Run basedpyright type-checking on a directory within a Bazel test."""

from __future__ import annotations

import subprocess
import sys


def main():
    """Run basedpyright on the given arguments."""
    result = subprocess.run(
        [sys.argv[1], *sys.argv[2:]],
        check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
