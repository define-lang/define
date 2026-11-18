"""Execute generated Define programs for codegen testdata."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_NO_ENVIRONMENT: Mapping[str, str] = types.MappingProxyType({})


def run_generated_program(
    generated_dir: Path,
    entry_script: str = "__main__.py",
    *,
    environment: Mapping[str, str] = _NO_ENVIRONMENT,
) -> subprocess.CompletedProcess[str]:
    """Execute a generated program and capture its process result.

    Args:
        generated_dir: The directory a program was generated into.
        entry_script: A script in that directory to run instead of the generated
            entry point, for a test that needs to start the program differently.
        environment: Variables to add to the program's environment, such as
            DEFINE_OPERATION_TRACE_FILE.
    """
    generated_dir = generated_dir.resolve()
    generated_environment = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join([str(generated_dir), *sys.path]),
    }
    # Windows can't start a program from a path of 260 characters or more, or
    # in a working directory that long, and a test's venv and testdata can be
    # that deep. The venv's python is a link to an interpreter with a shorter
    # path, and the program doesn't need the venv, since PYTHONPATH has every
    # import path. Nor does it depend on its working directory. From 247
    # characters, Windows also fails to load the interpreter's DLLs unless the
    # interpreter was started by its \\?\ path, which subprocess doesn't add.
    interpreter = os.path.realpath(sys.executable)
    return subprocess.run(
        [interpreter, str(generated_dir / entry_script)],
        executable="\\\\?\\" + interpreter if os.name == "nt" else None,
        cwd=tempfile.gettempdir(),
        env=os.environ | generated_environment | dict(environment),
        capture_output=True,
        text=True,
        check=False,
    )
