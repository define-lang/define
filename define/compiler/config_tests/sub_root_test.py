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

    assert test_helpers.load_project_root_config(
        _SUB_ROOT,
        test_helpers.declaring_entry("sub.example.com:lib", "subroot"),
    ) == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.SubRootNotProjectRootDiagnostic(
                config_path=str(config.LOCAL_DEPS_PATH),
                field_path=("deps", "local", 0, "path"),
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
            sub_roots={
                "mv:define-lang.org:lib": config.LocalDependencyEntry(
                    deps_path=str(_SUB_ROOT / config.LOCAL_DEPS_PATH),
                    index=0,
                    universe="mv:define-lang.org:lib",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/lib")),
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
                config_path=str(_SUB_ROOT / config.CONFIG_PATH),
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
                config_path=str(_SUB_ROOT / config.LOCAL_DEPS_PATH),
                field_path=("deps", "local", 0, "path"),
                violation_message="value is required",
            )
        ],
    )
