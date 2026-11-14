"""Resolving a project root's configuration."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler import constants
from define.compiler.config import config_loader, local_deps_config, project_config
from define.compiler.config_tests import test_helpers
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_resolves_fqun_and_sub_roots(
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
                ),
                "mv:define-lang.org:core": local_deps_config.LocalDependencyEntry(
                    universe="mv:define-lang.org:core",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/core")),
                    universe_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE,
                        ("deps", "local", 1, "universe_name"),
                    ),
                    path_location=test_helpers.config_field_location(
                        local_deps_config.CONFIG_FILE, ("deps", "local", 1, "path")
                    ),
                ),
            },
            value_encodings={},
            logical_operation_encoding_operations={},
        ),
        diagnostics=[],
    )


def test_missing_local_deps_resolves_empty_sub_roots(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=config_loader.Config(
            fqun="test.example.com:my_lib",
            fqun_location=test_helpers.config_field_location(
                project_config.CONFIG_FILE, ("project", "universe_name")
            ),
            sub_roots={},
            value_encodings={},
            logical_operation_encoding_operations={},
        ),
        diagnostics=[],
    )


def test_not_a_project_root(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.NotRunFromProjectRootDiagnostic(
                config_path=str(project_config.CONFIG_FILE.path),
            )
        ],
    )


def test_declaring_entry_universe_match_succeeds(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config(
        declaring_entry=test_helpers.declaring_entry("test.example.com:my_lib", ".")
    ) == config_loader.ConfigLoadResult(
        config=config_loader.Config(
            fqun="test.example.com:my_lib",
            fqun_location=test_helpers.config_field_location(
                project_config.CONFIG_FILE, ("project", "universe_name")
            ),
            sub_roots={},
            value_encodings={},
            logical_operation_encoding_operations={},
        ),
        diagnostics=[],
    )


def test_declaring_entry_universe_mismatch(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config(
        declaring_entry=test_helpers.declaring_entry("other.example.com:other_lib", ".")
    ) == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.SubRootFqunMismatchDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE, ("project", "universe_name")
                ),
                expected_fqun="other.example.com:other_lib",
                actual_fqun="test.example.com:my_lib",
                sub_root_path=str(constants.PROJECT_ROOT),
            )
        ],
    )
