"""Resolving a project root's configuration."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

from define.compiler import config, constants
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

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib",
            sub_roots={
                "mv:define-lang.org:lib": config.LocalDependencyEntry(
                    deps_path=str(config.LOCAL_DEPS_PATH),
                    index=0,
                    universe="mv:define-lang.org:lib",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/lib")),
                ),
                "mv:define-lang.org:core": config.LocalDependencyEntry(
                    deps_path=str(config.LOCAL_DEPS_PATH),
                    index=1,
                    universe="mv:define-lang.org:core",
                    path=define_path.DefinePathFromPosix(PurePosixPath("vendor/core")),
                ),
            },
        ),
        diagnostics=[],
    )


def test_missing_local_deps_resolves_empty_sub_roots(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib", sub_roots={}
        ),
        diagnostics=[],
    )


def test_not_a_project_root(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.NotRunFromProjectRootDiagnostic(
                config_path=str(config.CONFIG_PATH),
            )
        ],
    )


def test_declaring_entry_universe_match_succeeds(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config(
        declaring_entry=test_helpers.declaring_entry("test.example.com:my_lib", ".")
    ) == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib", sub_roots={}
        ),
        diagnostics=[],
    )


def test_declaring_entry_universe_mismatch(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config(
        declaring_entry=test_helpers.declaring_entry("other.example.com:other_lib", ".")
    ) == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.SubRootFqunMismatchDiagnostic(
                config_path=str(config.CONFIG_PATH),
                field_path=("project", "universe_name"),
                expected_fqun="other.example.com:other_lib",
                actual_fqun="test.example.com:my_lib",
                sub_root_path=str(constants.PROJECT_ROOT),
            )
        ],
    )
