# Rejected: ruff:PLW1510
# Rejected in mutation runs: nothing
"""A deleted `check=False`, which is what `subprocess.run` does without it."""

from __future__ import annotations

import subprocess


def succeeds(command: list[str]) -> bool:
    """Return whether `command` exits with 0."""
    return subprocess.run(command, capture_output=True).returncode == 0
