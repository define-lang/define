# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import exceptions, validator


def test_requires_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(exceptions.NotProjectRootError):
        validator.Validator().parse_and_validate_program(PurePosixPath("test.def"))


def test_not_project_root_error_includes_docs_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(exceptions.NotProjectRootError, match=r"project-root\.md"):
        validator.Validator().parse_and_validate_program(PurePosixPath("test.def"))


def test_invalid_project_config_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text("project: {}\n", encoding="utf-8")
    (tmp_path / "test.def").write_text(
        "define the potential position<x.com:lib:/test>.\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(exceptions.ConfigValidationError):
        validator.Validator().parse_and_validate_program(PurePosixPath("test.def"))
