# pyright: reportUnusedCallResult=false
"""Program configuration validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import config
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    import pytest


def test_requires_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"))
        .file_results
    )
    assert len(results) == 1
    assert isinstance(results[0].exception, config.NotProjectRootError)


def test_invalid_project_config_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text("project: {}\n", encoding="utf-8")
    (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = (
        program_validator.ProgramStructuralValidator()
        .validate_program(PurePosixPath("test.dfn"))
        .file_results
    )
    assert len(results) == 1
    assert isinstance(results[0].exception, config.ConfigValidationError)
