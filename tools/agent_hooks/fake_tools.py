"""Fake programs that the agent hook tests put on PATH in place of real ones."""

from __future__ import annotations

import os
import shutil
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import pytest

# Shell code for the directory that a fake program runs in, written the way
# Python writes paths on this platform.
WORKING_DIRECTORY = '$(cygpath -w "$PWD")' if sys.platform == "win32" else "$PWD"


def install(bin_directory: Path, name: str, script_lines: Sequence[str]):
    """Install a shell script that runs as the program `name`."""
    script = bin_directory / name
    _ = script.write_text(
        "\n".join(["#!/bin/sh", *script_lines]) + "\n", encoding="utf-8", newline="\n"
    )
    script.chmod(0o755)
    if sys.platform == "win32":
        # Windows finds programs only by extensions such as .cmd, and runs
        # shell scripts only through Git Bash.
        bash = shutil.which("bash")
        if bash is None:
            raise FileNotFoundError("Git Bash is required for these tests")
        _ = (bin_directory / f"{name}.cmd").write_text(
            f'@"{bash}" "%~dp0{name}" %*\r\n', encoding="utf-8", newline=""
        )


def put_first_on_path(monkeypatch: pytest.MonkeyPatch, directory: Path):
    """Make the programs in `directory` take the place of any others."""
    monkeypatch.setenv("PATH", os.pathsep.join([str(directory), os.environ["PATH"]]))
