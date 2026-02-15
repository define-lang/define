"""Run basedpyright type-checking on a directory within a Bazel test."""

import subprocess
import sys


def main():
    """Run basedpyright on the given arguments."""
    result = subprocess.run(
        [sys.argv[1], *sys.argv[2:]],
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
