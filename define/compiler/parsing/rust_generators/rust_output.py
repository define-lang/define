"""Writes generated Rust code."""

from __future__ import annotations

import os
import pathlib
import subprocess

# A generator finds its own runfiles through these variables. rustfmt has
# runfiles of its own, which it finds next to its executable only when these
# variables are not set.
_RUNFILES_VARIABLES = frozenset(
    {"JAVA_RUNFILES", "RUNFILES_DIR", "RUNFILES_MANIFEST_FILE"}
)


def write(path: str, code: str, rustfmt: str):
    """Write `code` to `path`, and format it with the rustfmt program at `rustfmt`."""
    output = pathlib.Path(path)
    _ = output.write_text(code, encoding="utf-8", newline="\n")
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in _RUNFILES_VARIABLES
    }
    _ = subprocess.run(
        [rustfmt, "--edition", "2024", output], env=environment, check=True
    )
