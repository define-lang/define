"""Add the coverage of Python subprocesses to the coverage that a test measures."""

from __future__ import annotations

import contextlib
import copy
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import coverage

if TYPE_CHECKING:
    from collections.abc import Generator

# A Python subprocess imports this module at startup when it finds it on its
# PYTHONPATH.
_STARTUP_MODULE = "import coverage\n\ncoverage.process_startup()\n"


@contextlib.contextmanager
def measure_subprocesses() -> Generator[None]:
    """Add the coverage of the Python subprocesses started in this context to this process's coverage.

    A subprocess is measured only when this process measures coverage, and only
    when the subprocess's Python reads PYTHONPATH.
    """
    measured = coverage.Coverage.current()
    if measured is None:
        yield
        return
    with tempfile.TemporaryDirectory() as directory_name:
        directory = Path(directory_name)
        startup_directory = directory / "startup"
        startup_directory.mkdir()
        _ = (startup_directory / "sitecustomize.py").write_text(
            _STARTUP_MODULE, encoding="utf-8", newline="\n"
        )
        # The subprocess's own environment does not have coverage installed.
        (startup_directory / "coverage").symlink_to(
            Path(coverage.__file__).parent, target_is_directory=True
        )
        data_directory = directory / "data"
        data_directory.mkdir()
        config = copy.copy(measured.config)
        # Each subprocess writes its own data file, named after this process's
        # data file, so that combine finds them all.
        config.data_file = str(data_directory / Path(config.data_file).name)
        config.parallel = True
        original_environment = dict(os.environ)
        os.environ["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(startup_directory), os.environ.get("PYTHONPATH")])
        )
        os.environ["COVERAGE_PROCESS_CONFIG"] = config.serialize()
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(original_environment)
        measured.combine([str(data_directory)])
