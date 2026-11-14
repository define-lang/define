"""Loading a project's project config."""

from __future__ import annotations

import typing

from crates.source_rendering.python import rendering
from defcl.python import error_types, errors
from define.compiler.config import config_loader, local_deps_config, project_config
from define.compiler.config_tests import test_helpers
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_each_schema_error_is_a_diagnostic(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    assert result.config is None
    first, second = result.diagnostics
    assert isinstance(first, errors.UnknownFieldNameDiagnostic)
    assert first.location == rendering.SourceLocation(
        line=3,
        column=3,
        end_line=3,
        end_column=14,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert first.file_path == str(project_config.CONFIG_FILE.path)
    assert first.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
    assert first.field_name == "universe_nam"
    assert first.message_type == "define.config.project.Project"
    assert isinstance(second, errors.UnknownFieldNameDiagnostic)
    assert second.location == rendering.SourceLocation(
        line=4,
        column=3,
        end_line=4,
        end_column=7,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert second.file_path == str(project_config.CONFIG_FILE.path)
    assert second.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
    assert second.field_name == "owner"
    assert second.message_type == "define.config.project.Project"


def test_value_of_the_wrong_kind_is_a_diagnostic(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    assert result.config is None
    (diagnostic,) = result.diagnostics
    assert type(diagnostic) is errors.SemanticDiagnostic
    assert diagnostic.location == rendering.SourceLocation(
        line=2,
        column=18,
        end_line=2,
        end_column=18,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert diagnostic.file_path == str(project_config.CONFIG_FILE.path)
    assert (
        diagnostic.kind
        == error_types.SemanticDiagnosticKind.NON_STRING_FOR_STRING_FIELD
    )
    assert diagnostic.field_name == "universe_name"


def test_empty_universe_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE, ("project", "universe_name")
                ),
                field_path=("project", "universe_name"),
                violation_message="must be at least 1 characters",
            )
        ],
    )


def test_local_deps_diagnostics_reported_too(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE, ("project", "universe_name")
                ),
                field_path=("project", "universe_name"),
                violation_message="must be at least 1 characters",
            ),
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not be absolute",
            ),
        ],
    )


def test_syntax_error(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    assert result.config is None
    (diagnostic,) = result.diagnostics
    assert isinstance(diagnostic, errors.SyntaxDiagnostic)
    assert diagnostic.location == rendering.SourceLocation(
        line=2,
        column=16,
        end_line=2,
        end_column=16,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert diagnostic.file_path == str(project_config.CONFIG_FILE.path)
    assert diagnostic.kind == error_types.SyntaxDiagnosticKind.MISSING_COLON


def test_layout_error_still_resolves(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    assert result.config == config_loader.Config(
        fqun="test.example.com:my_lib",
        fqun_location=test_helpers.config_field_location(
            project_config.CONFIG_FILE, ("project", "universe_name")
        ),
        sub_roots={},
        value_encodings={},
        logical_operation_encoding_operations={},
    )
    (diagnostic,) = result.diagnostics
    assert type(diagnostic) is errors.SyntaxDiagnostic
    assert diagnostic.kind == error_types.SyntaxDiagnosticKind.BLANK_LINE
    assert diagnostic.location == rendering.SourceLocation(
        line=3,
        column=1,
        end_line=3,
        end_column=1,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert diagnostic.file_path == str(project_config.CONFIG_FILE.path)


def test_layout_error_and_rule_violation(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    assert result.config is None
    blank_line, violation = result.diagnostics
    assert type(blank_line) is errors.SyntaxDiagnostic
    assert blank_line.kind == error_types.SyntaxDiagnosticKind.BLANK_LINE
    assert blank_line.location == rendering.SourceLocation(
        line=3,
        column=1,
        end_line=3,
        end_column=1,
        file_path=str(project_config.CONFIG_FILE.path),
    )
    assert blank_line.file_path == str(project_config.CONFIG_FILE.path)
    assert violation == diagnostics.ConfigViolationDiagnostic(
        location=test_helpers.config_field_location(
            project_config.CONFIG_FILE, ("project", "universe_name")
        ),
        field_path=("project", "universe_name"),
        violation_message="must be at least 1 characters",
    )
