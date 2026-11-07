# pyright: reportUnusedCallResult=false
"""Program configuration validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import ast
from define.compiler.errors import diagnostics
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_requires_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.all_diagnostics == [
        diagnostics.NotRunFromProjectRootDiagnostic(
            location=ast.start_of_file_location(
                PurePosixPath(".define/project/config.defcl")
            ),
            config_path=".define/project/config.defcl",
        )
    ]


def test_invalid_project_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text(
        "project: {}\n", encoding="utf-8", newline="\n"
    )
    (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert result.all_exceptions == []
    assert len(result.file_results) == 1
    assert result.all_diagnostics == [
        diagnostics.InvalidConfigDiagnostic(
            location=ast.start_of_file_location(
                PurePosixPath(".define/project/config.defcl")
            ),
            violation_messages=["project.universe_name: value is required"],
        )
    ]
