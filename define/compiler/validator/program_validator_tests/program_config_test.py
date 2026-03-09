# pyright: reportUnusedCallResult=false
"""Program configuration validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import exceptions
from define.compiler.validator import program_validator


def test_requires_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert isinstance(results[0].exception, exceptions.NotProjectRootError)


def test_invalid_project_config_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text("project: {}\n", encoding="utf-8")
    (tmp_path / "test.def").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    assert len(results) == 1
    assert isinstance(results[0].exception, exceptions.ConfigValidationError)
