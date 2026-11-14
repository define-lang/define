"""Loading a project's Value Encoding Associations."""

from __future__ import annotations

import typing

from crates.source_rendering.python import rendering
from define.compiler import config
from define.compiler.config_tests import test_helpers
from define.compiler.errors import diagnostics, syntax_errors

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_resolves_value_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    () = result.diagnostics
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {
        "/number/integer": [
            test_helpers.encoding_name("/number/integer/twos_complement", 5)
        ],
        "/number/natural": [
            test_helpers.encoding_name("/number/integer/twos_complement", 9),
            test_helpers.encoding_name("/number/integer/unsigned", 13),
        ],
    }


def test_has_encodings_false_does_not_read_encodings(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=config.ProjectRootConfig(
            fqun="test.example.com:my_lib",
            fqun_location=test_helpers.config_field_location(
                config.PROJECT_CONFIG, ("project", "universe_name")
            ),
            sub_roots={},
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
                location=test_helpers.config_field_location(
                    config.PROJECT_CONFIG, ("project", "associations", "has_encodings")
                ),
                encodings_config_path=str(config.ENCODINGS_PATH),
            )
        ],
    )


def test_value_in_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=15,
            end_line=4,
            end_column=35,
            file_path=str(config.ENCODINGS_PATH),
        ),
        field_name="value",
        name="other.com:lib:/number",
        fqun="test.example.com:my_lib",
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_value_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=4,
            column=15,
            end_line=4,
            end_column=20,
            file_path=str(config.ENCODINGS_PATH),
        )
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_value_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=15,
            end_line=4,
            end_column=37,
            file_path=str(config.ENCODINGS_PATH),
        ),
        fqun="test.example.com:my_lib",
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_resolves_encoding_from_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    () = result.diagnostics
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {
        "/number": [test_helpers.encoding_name("other.com:lib:/number/ascii", 5)]
    }


def test_encoding_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=29,
            file_path=str(config.ENCODINGS_PATH),
        )
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_encoding_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=40,
            file_path=str(config.ENCODINGS_PATH),
        ),
        fqun="test.example.com:my_lib",
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_unsorted_values(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.UnsortedValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            config.ENCODINGS_CONFIG, ("encodings", "value_encodings", 1, "value")
        ),
        value="/number/integer",
        previous_value="/number/natural",
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {
        "/number/natural": [test_helpers.encoding_name("/number/natural/ascii", 5)],
        "/number/integer": [test_helpers.encoding_name("/number/integer/ascii", 9)],
    }


def test_duplicate_value_encoding(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.DuplicateValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            config.ENCODINGS_CONFIG, ("encodings", "value_encodings", 1)
        ),
        value="/number",
        encoding="/number/ascii",
        first_location=test_helpers.config_field_location(
            config.ENCODINGS_CONFIG, ("encodings", "value_encodings", 0)
        ),
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {
        "/number": [test_helpers.encoding_name("/number/ascii", 5)]
    }


def test_duplicate_value_encoding_with_invalid_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_project_root_config()
    first_name, second_name, duplicate = result.diagnostics
    assert first_name == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=5,
            column=18,
            end_line=5,
            end_column=29,
            file_path=str(config.ENCODINGS_PATH),
        )
    )
    assert second_name == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=9,
            column=18,
            end_line=9,
            end_column=29,
            file_path=str(config.ENCODINGS_PATH),
        )
    )
    assert duplicate == diagnostics.DuplicateValueEncodingDiagnostic(
        location=test_helpers.config_field_location(
            config.ENCODINGS_CONFIG, ("encodings", "value_encodings", 1)
        ),
        value="/number",
        encoding="number/ascii",
        first_location=test_helpers.config_field_location(
            config.ENCODINGS_CONFIG, ("encodings", "value_encodings", 0)
        ),
    )
    assert result.root_config is not None
    assert result.root_config.fqun == "test.example.com:my_lib"
    assert result.root_config.sub_roots == {}
    assert test_helpers.encoding_names(result.root_config.value_encodings) == {}


def test_local_deps_and_encodings_diagnostics(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_project_root_config() == config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    config.LOCAL_DEPS_CONFIG, ("deps", "local", 0, "path")
                ),
                field_path=("deps", "local", 0, "path"),
                violation_message="path must not be absolute",
            ),
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    config.ENCODINGS_CONFIG,
                    ("encodings", "value_encodings", 0, "encoding"),
                ),
                field_path=("encodings", "value_encodings", 0, "encoding"),
                violation_message="value is required",
            ),
        ],
    )
