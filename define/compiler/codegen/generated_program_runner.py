"""Execute generated Define programs for codegen testdata."""

from __future__ import annotations

import os
import subprocess
import sys
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
    generated_environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
    }
    if operation_trace_file is not None:
        generated_environment["DEFINE_OPERATION_TRACE_FILE"] = str(operation_trace_file)
    return subprocess.run(
        [sys.executable, str(generated_dir / entry_script)],
        env=os.environ | generated_environment,
        capture_output=True,
        text=True,
        check=False,
    )
