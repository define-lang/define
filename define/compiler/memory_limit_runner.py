"""Run a command with a Linux data-segment limit."""

import os
import resource
import sys


def main():
    """Apply the limit and replace this process with the requested command."""
    data_limit_bytes = int(sys.argv[1])
    command = sys.argv[2:]
    resource.setrlimit(
        resource.RLIMIT_DATA,
        (data_limit_bytes, data_limit_bytes),
    )
    os.execv(command[0], command)  # noqa: S606


if __name__ == "__main__":
    main()
