# pyright: reportUnusedCallResult=false
"""Integration tests that run the real compiler binary against real stdin pipes.

Unlike main_test.py (which mocks the driver and uses CliRunner's in-memory
stdin), these tests launch the built binary in a subprocess so the stdin
detection runs against a genuine OS pipe and /dev/null.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from define.compiler import test_runfiles

if TYPE_CHECKING:
    from pathlib import Path

_USAGE_ERROR = 2
_POSITION_SOURCE = "define the potential position<my.domain.com:my_lib:/test>.\n"
_CONSTRUCTOR_SOURCE = (
    "define the potential action<my.domain.com:my_lib:/test> {\n"
    "    define the position<output>.\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        create a particle in position<output>.\n"
    "    }\n"
    "}\n"
)


def _binary_path() -> Path:
    return test_runfiles.resolve_from_env("MAIN_BINARY")


def _setup_project(tmp_path: Path, source: str = _POSITION_SOURCE) -> None:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text(
        'project: {\n  universe_name: "my.domain.com:my_lib"\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "test.dfn").write_text(source, encoding="utf-8")


class TestStdinPipe:
    def test_piped_source_without_file_validates(self, tmp_path: Path):
        _setup_project(tmp_path)
        result = subprocess.run(
            [str(_binary_path()), "validate"],
            input=_POSITION_SOURCE,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr

    def test_piped_source_with_file_is_error(self, tmp_path: Path):
        _setup_project(tmp_path)
        result = subprocess.run(
            [str(_binary_path()), "validate", "test.dfn"],
            input=_POSITION_SOURCE,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == _USAGE_ERROR
        assert "not both" in result.stderr

    def test_file_with_devnull_stdin_validates(self, tmp_path: Path):
        _setup_project(tmp_path)
        result = subprocess.run(
            [str(_binary_path()), "validate", "test.dfn"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr

    def test_file_with_open_pipe_does_not_block(self, tmp_path: Path):
        _setup_project(tmp_path)
        read_fd, write_fd = os.pipe()
        try:
            result = subprocess.run(
                [str(_binary_path()), "validate", "test.dfn"],
                stdin=read_fd,
                capture_output=True,
                check=False,
                text=True,
                cwd=tmp_path,
                timeout=30,
            )
        finally:
            os.close(read_fd)
            os.close(write_fd)
        assert result.returncode == _USAGE_ERROR
        assert "not both" in result.stderr

    def test_no_file_with_devnull_stdin_is_error(self, tmp_path: Path):
        _setup_project(tmp_path)
        result = subprocess.run(
            [str(_binary_path()), "validate"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == _USAGE_ERROR
        assert "no input" in result.stderr

    def test_file_compiles_to_output_dir(self, tmp_path: Path):
        _setup_project(tmp_path, _CONSTRUCTOR_SOURCE)
        output_dir = tmp_path / "out"
        result = subprocess.run(
            [str(_binary_path()), "compile", "test.dfn", "--out", str(output_dir)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert (output_dir / "__main__.py").exists()

    def test_piped_source_compiles_to_output_dir(self, tmp_path: Path):
        output_dir = tmp_path / "out"
        result = subprocess.run(
            [str(_binary_path()), "compile", "--out", str(output_dir)],
            input=_CONSTRUCTOR_SOURCE,
            capture_output=True,
            check=False,
            text=True,
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stderr
        assert (output_dir / "__main__.py").exists()
