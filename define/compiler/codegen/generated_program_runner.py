"""Execute generated Define programs for codegen testdata."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def run_generated_program(
    generated_dir: Path,
    entry_script: str = "__main__.py",
    *,
    operation_trace_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a generated program and capture its process result.

    Args:
        generated_dir: The directory a program was generated into.
        entry_script: A script in that directory to run instead of the generated
            entry point, for a test that needs to start the program differently.
        operation_trace_file: A file to receive the generated program's ordered
            Particle Operation trace.
    """
    generated_dir = generated_dir.resolve()
    generated_environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
    }
    if operation_trace_file is not None:
        generated_environment["DEFINE_OPERATION_TRACE_FILE"] = str(operation_trace_file)
    # Windows can't start a program from a path of 260 characters or more, or
    # in a working directory that long, and a test's venv and testdata can be
    # that deep. The venv's python is a link to an interpreter with a shorter
    # path, and the program doesn't need the venv, since PYTHONPATH has every
    # import path. Nor does it depend on its working directory.
    return subprocess.run(
        [os.path.realpath(sys.executable), str(generated_dir / entry_script)],
        cwd=tempfile.gettempdir(),
        env=os.environ | generated_environment,
        capture_output=True,
        text=True,
        check=False,
    )
