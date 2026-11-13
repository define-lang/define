"""Loading the configuration of a sub-root."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler import config
from define.compiler.config_tests import test_helpers
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest

_SUB_ROOT = define_path.DefinePath("subroot")


def test_not_a_project_root(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)
    declaring_entry = test_helpers.declaring_entry("sub.example.com:lib", "subroot")

    assert test_helpers.load_project_root_config(
        _SUB_ROOT, declaring_entry
    ) == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.SubRootNotProjectRootDiagnostic(
                location=declaring_entry.path_location,
                sub_root_path=str(_SUB_ROOT),
                sub_root_config_path=str(_SUB_ROOT / config.CONFIG_PATH),
            )
        ],
    )


def test_resolves_fqun_and_sub_roots(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config(_SUB_ROOT) == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="sub.example.com:lib",
            fqun_location=test_helpers.config_field_location(
                config.PROJECT_CONFIG, ("project", "universe_name"), root=_SUB_ROOT
            ),
            sub_roots={
                "mv:define-lang.org:lib": config.LocalDependencyEntry(
                    universe="mv:define-lang.org:lib",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/lib")),
                    universe_location=test_helpers.config_field_location(
                        config.LOCAL_DEPS_CONFIG,
                        ("deps", "local", 0, "universe_name"),
                        root=_SUB_ROOT,
                    ),
                    path_location=test_helpers.config_field_location(
                        config.LOCAL_DEPS_CONFIG,
                        ("deps", "local", 0, "path"),
                        root=_SUB_ROOT,
                    ),
                )
            },
        ),
        diagnostics=[],
    )


def test_project_config_validation_error(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config(_SUB_ROOT) == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    config.PROJECT_CONFIG, ("project", "universe_name"), root=_SUB_ROOT
                ),
                field_path=("project", "universe_name"),
                violation_message="must be at least 1 characters",
            )
        ],
    )


def test_local_deps_validation_error(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config(_SUB_ROOT) == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    config.LOCAL_DEPS_CONFIG,
                    ("deps", "local", 0, "path"),
                    root=_SUB_ROOT,
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="value is required",
            )
        ],
    )
