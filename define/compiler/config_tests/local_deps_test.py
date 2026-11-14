"""Loading a project's local dependency overrides."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from crates.source_rendering.python import rendering
from defcl.python import error_types, errors
from define.compiler.config import config_loader, local_deps_config, project_config
from define.compiler.config_tests import test_helpers
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_missing_universe_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "universe_name")
                ),
                field_path=("deps", "local", 0, "universe_name"),
                violation_message="value is required",
            )
        ],
    )


def test_empty_universe_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "universe_name")
                ),
                field_path=("deps", "local", 0, "universe_name"),
                violation_message="must be at least 1 characters",
            )
        ],
    )


def test_missing_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="value is required",
            )
        ],
    )


def test_absolute_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not be absolute",
            )
        ],
    )


def test_dotdot_part_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not have a '..' part",
            )
        ],
    )


def test_leading_dotdot_part_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not have a '..' part",
            )
        ],
    )


def test_dot_part_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not have a '.' part",
            )
        ],
    )


def test_dot_path(testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not have a '.' part",
            )
        ],
    )


def test_empty_part_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not contain '//'",
            )
        ],
    )


def test_backslash_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not contain a backslash",
            )
        ],
    )


def test_dots_within_a_part_of_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=config_loader.Config(
            fqun="test.example.com:my_lib",
            fqun_location=test_helpers.config_field_location(
                project_config.CONFIG_FILE, ("project", "universe_name")
            ),
            sub_roots={
                "mv:define-lang.org:lib": local_deps_config.LocalDependencyEntry(
                    universe="mv:define-lang.org:lib",
                    path=define_path.DefinePathFromPosix(
                        PurePosixPath("vendor/lib..v2/.hidden")
                    ),
                    universe_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE,
                        ("deps", "local", 0, "universe_name"),
                    ),
                    path_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                    ),
                ),
            },
            value_encodings={},
        ),
        diagnostics=[],
    )


def test_trailing_slash_in_path(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not end with '/'",
            )
        ],
    )


def test_duplicate_universe_name_uses_the_first_entry(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=config_loader.Config(
            fqun="test.example.com:my_lib",
            fqun_location=test_helpers.config_field_location(
                project_config.CONFIG_FILE, ("project", "universe_name")
            ),
            sub_roots={
                "mv:define-lang.org:lib": local_deps_config.LocalDependencyEntry(
                    universe="mv:define-lang.org:lib",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/lib")),
                    universe_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE,
                        ("deps", "local", 0, "universe_name"),
                    ),
                    path_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE, ("deps", "local", 0, "path")
                    ),
                )
            },
            value_encodings={},
        ),
        diagnostics=[
            diagnostics.DuplicateLocalDependencyDiagnostic(
                location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 1, "universe_name")
                ),
                universe_name="mv:define-lang.org:lib",
                first_location=test_helpers.config_field_location(
                    local_deps_config.CONFIG_FILE, ("deps", "local", 0, "universe_name")
                ),
            )
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
        line=4,
        column=22,
        end_line=4,
        end_column=26,
        file_path=str(local_deps_config.CONFIG_FILE.path),
    )
    assert diagnostic.file_path == str(local_deps_config.CONFIG_FILE.path)
    assert diagnostic.kind == error_types.SyntaxDiagnosticKind.SINGLE_QUOTES_NOT_ALLOWED
