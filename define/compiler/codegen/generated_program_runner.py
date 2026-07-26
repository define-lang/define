"""Execute generated Define programs for codegen testdata."""

import os
import subprocess
import sys
from pathlib import Path


def run_generated_program(
    generated_dir: Path,
    entry_script: str = "__main__.py",
) -> subprocess.CompletedProcess[str]:
    """Execute a generated program and capture its occupied positions.

    Args:
        generated_dir: The directory a program was generated into.
        entry_script: A script in that directory to run instead of the generated
            entry point, for a test that needs to start the program differently.
    """
    return subprocess.run(
        [sys.executable, str(generated_dir / entry_script)],
        env=os.environ
        | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
            "DEFINE_REPORT_OCCUPIED_POSITIONS": "1",
        },
        capture_output=True,
        text=True,
    )
