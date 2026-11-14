"""Loading a project's Encoding Operation associations."""

from __future__ import annotations

import typing

from crates.source_rendering.python import rendering
from define.compiler.config import (
    config_loader,
    encoding_operations_config,
    project_config,
)
from define.compiler.config_tests import test_helpers
from define.compiler.errors import diagnostics, syntax_errors

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_resolves_encoding_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    () = result.diagnostics
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert test_helpers.associated_names(result.config.value_encodings) == {}
    assert test_helpers.associated_names(
        result.config.logical_operation_encoding_operations
    ) == {
        "/number/add": [
            test_helpers.encoding_operation_name("/number/integer/add", 5),
            test_helpers.encoding_operation_name(
                "other.com:lib:/number/natural/add", 9
            ),
        ],
        "/number/negate": [
            test_helpers.encoding_operation_name("/number/integer/negate", 13)
        ],
    }


def test_missing_encoding_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.EncodingOperationsConfigNotFoundDiagnostic(
                location=test_helpers.config_field_location(
                    project_config.CONFIG_FILE,
                    ("project", "associations", "has_encoding_operations"),
                ),
                encoding_operations_config_path=str(
                    encoding_operations_config.CONFIG_FILE.path
                ),
            )
        ],
    )


def test_logical_operation_in_another_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.AssociationNameInAnotherUniverseDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=27,
            end_line=4,
            end_column=51,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        ),
        field_name="logical_operation",
        name="other.com:lib:/number/add",
        fqun="test.example.com:my_lib",
    )
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert (
        test_helpers.associated_names(
            result.config.logical_operation_encoding_operations
        )
        == {}
    )


def test_logical_operation_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=4,
            column=27,
            end_line=4,
            end_column=36,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        )
    )
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert (
        test_helpers.associated_names(
            result.config.logical_operation_encoding_operations
        )
        == {}
    )


def test_logical_operation_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
        location=rendering.SourceLocation(
            line=4,
            column=27,
            end_line=4,
            end_column=49,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        ),
        fqun="test.example.com:my_lib",
    )
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert (
        test_helpers.associated_names(
            result.config.logical_operation_encoding_operations
        )
        == {}
    )


def test_encoding_operation_that_is_not_a_global_name(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == syntax_errors.InvalidGlobalName(
        location=rendering.SourceLocation(
            line=5,
            column=28,
            end_line=5,
            end_column=45,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        )
    )
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert (
        test_helpers.associated_names(
            result.config.logical_operation_encoding_operations
        )
        == {}
    )


def test_encoding_operation_full_name_in_own_universe(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.GlobalReferenceMustUseShortFormDiagnostic(
        location=rendering.SourceLocation(
            line=5,
            column=28,
            end_line=5,
            end_column=50,
            file_path=str(encoding_operations_config.CONFIG_FILE.path),
        ),
        fqun="test.example.com:my_lib",
    )
    assert result.config is not None
    assert result.config.fqun == "test.example.com:my_lib"
    assert result.config.sub_roots == {}
    assert (
        test_helpers.associated_names(
            result.config.logical_operation_encoding_operations
        )
        == {}
    )


def test_unsorted_logical_operations(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.UnsortedEncodingOperationDiagnostic(
        location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 1, "logical_operation"),
        ),
        logical_operation="/number/add",
        previous_logical_operation="/number/negate",
    )
    assert result.config is not None
    assert test_helpers.associated_names(
        result.config.logical_operation_encoding_operations
    ) == {
        "/number/negate": [
            test_helpers.encoding_operation_name("/number/integer/negate", 5)
        ],
        "/number/add": [test_helpers.encoding_operation_name("/number/integer/add", 9)],
    }


def test_duplicate_encoding_operation(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    result = test_helpers.load_config()
    (diagnostic,) = result.diagnostics
    assert diagnostic == diagnostics.DuplicateEncodingOperationDiagnostic(
        location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 1),
        ),
        logical_operation="/number/add",
        encoding_operation="/number/integer/add",
        first_location=test_helpers.config_field_location(
            encoding_operations_config.CONFIG_FILE,
            ("encoding_operations", "operation_encodings", 0),
        ),
    )
    assert result.config is not None
    assert test_helpers.associated_names(
        result.config.logical_operation_encoding_operations
    ) == {
        "/number/add": [test_helpers.encoding_operation_name("/number/integer/add", 5)]
    }


def test_encoding_operation_missing(
    testdata_project_directory: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(testdata_project_directory)

    assert test_helpers.load_config() == config_loader.ConfigLoadResult(
        config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                location=test_helpers.config_field_location(
                    encoding_operations_config.CONFIG_FILE,
                    (
                        "encoding_operations",
                        "operation_encodings",
                        0,
                        "encoding_operation",
                    ),
                ),
                field_path=(
                    "encoding_operations",
                    "operation_encodings",
                    0,
                    "encoding_operation",
                ),
                violation_message="value is required",
            )
        ],
    )
