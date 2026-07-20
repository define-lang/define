"""Execute generated Define programs for codegen testdata."""

import os
import subprocess
import sys
from pathlib import Path


def run_generated_program(
    generated_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Execute a generated program and capture its occupied positions."""
    return subprocess.run(
        [sys.executable, str(generated_dir / "__main__.py")],
        env=os.environ
        | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
            "DEFINE_REPORT_OCCUPIED_POSITIONS": "1",
        },
        capture_output=True,
        text=True,
    )
