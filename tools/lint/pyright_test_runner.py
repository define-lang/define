"""Run pyright type-checking on a directory within a Bazel test."""

import subprocess
import sys


def main():
    """Run pyright on the given arguments."""
    result = subprocess.run(
        [sys.executable, "-m", "pyright", *sys.argv[1:]],
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
