"""Execute generated Define programs for codegen testdata."""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeneratedProgramResult:
    """The outcome of executing a generated program."""

    process: subprocess.CompletedProcess[str]
    occupied_positions: str


def run_generated_program(
    generated_dir: Path,
    entry_script: str = "__main__.py",
    *,
    trace_file: Path | None = None,
    max_threads: int | None = None,
) -> GeneratedProgramResult:
    """Execute a generated program and capture its occupied positions.

    Args:
        generated_dir: The directory a program was generated into.
        entry_script: A script in that directory to run instead of the generated
            entry point, for a test that needs to start the program differently.
        trace_file: A file to receive the generated program's operation trace.
        max_threads: The maximum scheduler threads for this execution.
    """
    # Closing the file leaves it in place for the generated program to write,
    # and it is still removed when this block ends.
    with tempfile.NamedTemporaryFile(delete_on_close=False) as report_file:
        report_file.close()
        generated_environment = {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
            "DEFINE_REPORT_OCCUPIED_POSITIONS": report_file.name,
        }
        if trace_file is not None:
            generated_environment["DEFINE_OPERATION_TRACE_FILE"] = str(trace_file)
        if max_threads is not None:
            generated_environment["DEFINE_MAX_THREADS"] = str(max_threads)
        process = subprocess.run(
            [sys.executable, str(generated_dir / entry_script)],
            env=os.environ | generated_environment,
            capture_output=True,
            text=True,
            check=False,
        )
        occupied_positions = Path(report_file.name).read_text()
    return GeneratedProgramResult(
        process=process, occupied_positions=occupied_positions
    )
