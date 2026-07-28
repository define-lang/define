"""Execute generated Define programs for codegen testdata."""

import os
import subprocess
import sys
from pathlib import Path


def run_generated_program(
    generated_dir: Path,
    entry_script: str = "__main__.py",
    *,
    trace_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute a generated program and capture its occupied positions.

    Args:
        generated_dir: The directory a program was generated into.
        entry_script: A script in that directory to run instead of the generated
            entry point, for a test that needs to start the program differently.
        trace_file: A file to receive the generated program's operation trace.
    """
    generated_environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
        # TODO: Make this generate to an output file if truthy.
        "DEFINE_REPORT_OCCUPIED_POSITIONS": "1",
    }
    if trace_file is not None:
        generated_environment["DEFINE_OPERATION_TRACE_FILE"] = str(trace_file)
    return subprocess.run(
        [sys.executable, str(generated_dir / entry_script)],
        env=os.environ | generated_environment,
        capture_output=True,
        text=True,
        check=False,
    )
