"""Entry point for the Define compiler."""

import sys
from pathlib import Path

from define.compiler import driver


def main() -> int:
    """Run the Define compiler CLI."""
    if len(sys.argv) < 2:
        print("Usage: main <file.def>", file=sys.stderr)
        return 2  # Usual error code for bad usage.

    d = driver.Driver()
    return d.run(Path(sys.argv[1]), sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
