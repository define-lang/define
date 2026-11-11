"""Loading a project's Value Encoding Associations."""

from __future__ import annotations

import typing

from define.compiler import config
from define.compiler.config_tests import test_helpers
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_resolves_value_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib",
            sub_roots={},
            value_encodings={
                "/number/integer": ["/number/integer/twos_complement"],
                "/number/natural": [
                    "/number/integer/twos_complement",
                    "/number/integer/unsigned",
                ],
            },
        ),
        diagnostics=[],
    )


def test_has_encodings_false_does_not_read_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib", sub_roots={}
        ),
        diagnostics=[],
    )


def test_missing_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.EncodingsConfigNotFoundDiagnostic(
                config_path=str(config.CONFIG_PATH),
                field_path=("project", "associations", "has_encodings"),
                encodings_config_path=str(config.ENCODINGS_PATH),
            )
        ],
    )


def test_value_that_is_not_a_short_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                config_path=str(config.ENCODINGS_PATH),
                field_path=("encodings", "value_encodings", 0, "value"),
                violation_message=(
                    "value must be a short global name, starting with '/'"
                ),
            )
        ],
    )


def test_encoding_that_is_not_a_short_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                config_path=str(config.ENCODINGS_PATH),
                field_path=("encodings", "value_encodings", 0, "encoding"),
                violation_message=(
                    "encoding must be a short global name, starting with '/'"
                ),
            )
        ],
    )


def test_unsorted_values(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib",
            sub_roots={},
            value_encodings={
                "/number/integer": ["/number/integer/ascii"],
                "/number/natural": ["/number/natural/ascii"],
            },
        ),
        diagnostics=[
            diagnostics.UnsortedValueEncodingDiagnostic(
                config_path=str(config.ENCODINGS_PATH),
                field_path=("encodings", "value_encodings", 1, "value"),
                value="/number/integer",
                previous_value="/number/natural",
            )
        ],
    )


def test_duplicate_value_encoding(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib",
            sub_roots={},
            value_encodings={"/number": ["/number/ascii"]},
        ),
        diagnostics=[
            diagnostics.DuplicateValueEncodingDiagnostic(
                config_path=str(config.ENCODINGS_PATH),
                field_path=("encodings", "value_encodings", 1),
                value="/number",
                encoding="/number/ascii",
                first_field_path=("encodings", "value_encodings", 0),
            )
        ],
    )


def test_local_deps_and_encodings_diagnostics(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                config_path=str(config.LOCAL_DEPS_PATH),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not be absolute",
            ),
            diagnostics.ConfigViolationDiagnostic(
                config_path=str(config.ENCODINGS_PATH),
                field_path=("encodings", "value_encodings", 0, "value"),
                violation_message=(
                    "value must be a short global name, starting with '/'"
                ),
            ),
        ],
    )
