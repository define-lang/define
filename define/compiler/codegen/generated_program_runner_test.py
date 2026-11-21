"""Tests for running a generated program."""

from __future__ import annotations

import os
import pathlib
import shutil
import sys
from typing import TYPE_CHECKING

from define.compiler.codegen import generated_program_runner

if TYPE_CHECKING:
    import pytest

# Windows can't start a program whose path has 260 characters or more, or start
# a program in a working directory whose path is that long. These names make a
# path below a test's temporary directory at least that long.
_LONG_DIRECTORY_NAMES = ["directory_with_a_long_name" * 2] * 6


def test_failing_program_returns_its_result(tmp_path: pathlib.Path):
    _ = (tmp_path / "__main__.py").write_text(
        "import sys\nprint('partial output')\nprint('program failed', file=sys.stderr)\nsys.exit(1)\n",
        encoding="utf-8",
        newline="\n",
    )

    result = generated_program_runner.run_generated_program(tmp_path)

    assert result.returncode == 1
    assert result.stdout == "partial output\n"
    assert result.stderr == "program failed\n"


def test_entry_script_imports_from_the_generated_directory(tmp_path: pathlib.Path):
    _ = (tmp_path / "generated_module.py").write_text(
        "MESSAGE = 'imported'\n", encoding="utf-8", newline="\n"
    )
    (tmp_path / "scripts").mkdir()
    _ = (tmp_path / "scripts" / "entry.py").write_text(
        "import generated_module\nprint(generated_module.MESSAGE)\n",
        encoding="utf-8",
        newline="\n",
    )

    result = generated_program_runner.run_generated_program(
        tmp_path, "scripts/entry.py"
    )

    assert result.returncode == 0
    assert result.stdout == "imported\n"
    assert result.stderr == ""


def test_program_runs_while_the_current_directory_path_is_long(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    _ = (tmp_path / "__main__.py").write_text(
        "print('ran')\n", encoding="utf-8", newline="\n"
    )
    long_directory = tmp_path.joinpath(*_LONG_DIRECTORY_NAMES)
    long_directory.mkdir(parents=True)
    monkeypatch.chdir(long_directory)

    result = generated_program_runner.run_generated_program(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "ran\n"


def test_program_runs_with_an_interpreter_whose_path_is_long(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    _ = (generated_dir / "__main__.py").write_text(
        "print('ran')\n", encoding="utf-8", newline="\n"
    )
    interpreter = pathlib.Path(os.path.realpath(sys.executable))
    long_directory = tmp_path.joinpath(*_LONG_DIRECTORY_NAMES)
    long_directory.mkdir(parents=True)
    # Windows loads an interpreter's DLLs from the interpreter's directory.
    for entry in interpreter.parent.iterdir():
        if entry == interpreter or entry.suffix in {".exe", ".dll"}:
            _ = shutil.copy2(entry, long_directory)
    monkeypatch.setattr(sys, "executable", str(long_directory / interpreter.name))

    result = generated_program_runner.run_generated_program(
        generated_dir, environment={"PYTHONHOME": sys.base_prefix}
    )

    assert result.returncode == 0
    assert result.stdout == "ran\n"
