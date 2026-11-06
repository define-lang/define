from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools import runfiles
from tools.agent_hooks import fake_tools

_PYTHONS = ("python3", "python", "py")


def _install_stub(bin_directory: Path, name: str):
    # This is what Windows' Microsoft Store stubs do.
    fake_tools.install(
        bin_directory, name, ["echo 'Python was not found' >&2", "exit 9009"]
    )


def _run(bin_directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(
        [bash, runfiles.resolve_from_env("RUN_PYTHON"), *arguments],
        check=False,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PATH": str(bin_directory)},
    )


@pytest.mark.parametrize("working_python", _PYTHONS)
def test_runs_the_first_python_that_works_in_isolated_mode(
    tmp_path: Path, working_python: str
):
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    for name in _PYTHONS[: _PYTHONS.index(working_python)]:
        _install_stub(bin_directory, name)
    fake_tools.install(
        bin_directory,
        working_python,
        [f"exec '{Path(sys.executable).as_posix()}' \"$@\""],
    )
    script = tmp_path / "script.py"
    _ = script.write_text(
        "import json, sys\nprint(json.dumps([sys.argv[1:], sys.flags.isolated]))\n",
        encoding="utf-8",
        newline="\n",
    )

    result = _run(bin_directory, str(script), "two words")

    assert (result.returncode, json.loads(result.stdout), result.stderr) == (
        0,
        [["two words"], 1],
        "",
    )


def test_fails_when_no_python_works(tmp_path: Path):
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    for name in _PYTHONS:
        _install_stub(bin_directory, name)

    result = _run(bin_directory, "script.py")

    assert (result.returncode, result.stdout, result.stderr) == (
        1,
        "",
        "The agent hooks need Python 3 on PATH as python3, python or py.\n",
    )
