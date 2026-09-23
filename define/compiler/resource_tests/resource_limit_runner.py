"""Run a command with Linux CPU and data-segment limits."""

from __future__ import annotations

import os
import resource
import sys


def main():
    """Apply limits and replace this process with the requested command."""
    data_limit_bytes = int(sys.argv[1])
    cpu_seconds = int(sys.argv[2])
    command = sys.argv[3:]
    resource.setrlimit(
        resource.RLIMIT_DATA,
        (data_limit_bytes, data_limit_bytes),
    )
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.execv(command[0], command)  # noqa: S606


if __name__ == "__main__":
    main()
