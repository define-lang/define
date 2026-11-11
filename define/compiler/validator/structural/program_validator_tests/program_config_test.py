# pyright: reportUnusedCallResult=false
"""Program configuration validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from crates.source_rendering.python import rendering
from defcl.python import error_types, errors
from define.compiler.errors import diagnostics
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_requires_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert result.file_results == []
    assert result.all_diagnostics == [
        diagnostics.NotRunFromProjectRootDiagnostic(
            config_path=".define/project/config.defcl",
        )
    ]


def test_invalid_project_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text(
        ('project: {\n  universe_name: ""\n}\n'),
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "test.dfn").write_text(
        "define the potential position<x.com:lib:/test>.\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    result = program_validator.validate_program(PurePosixPath("test.dfn"))
    assert result.file_results == []
    assert result.all_diagnostics == [
        diagnostics.ConfigViolationDiagnostic(
            config_path=".define/project/config.defcl",
            field_path=("project", "universe_name"),
            violation_message="must be at least 1 characters",
        )
    ]


def test_project_config_with_layout_error_is_still_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text(
        ('project: {\n  universe_name: "x.com:lib"\n\n}\n'),
        encoding="utf-8",
        newline="\n",
    )
    (tmp_path / "test.dfn").write_text(
        (
            "define the potential position<x.com:lib:/test>.\n"
            "define the potential position<x.com:lib:/test>.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    result = program_validator.validate_program(PurePosixPath("test.dfn"))
    blank_line, duplicate_definition = result.all_diagnostics
    assert type(blank_line) is errors.SyntaxDiagnostic
    assert blank_line.kind == error_types.SyntaxDiagnosticKind.BLANK_LINE
    assert blank_line.location == rendering.SourceLocation(
        line=3,
        column=1,
        end_line=3,
        end_column=1,
        file_path=".define/project/config.defcl",
    )
    assert blank_line.file_path == ".define/project/config.defcl"
    assert duplicate_definition == diagnostics.DuplicateDefinitionDiagnostic(
        location=rendering.SourceLocation(
            line=2, column=1, end_line=2, end_column=47, file_path="test.dfn"
        ),
        definition_type="position",
        path="/test",
        first_definition_line=1,
    )
